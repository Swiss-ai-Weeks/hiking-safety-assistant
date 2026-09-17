"""The live `Narrator`: an OpenAI-compatible chat completions endpoint, behind the copy rules.

Nothing here can fail an assessment. Narration off, no endpoint, a timeout, a 500, an answer that is
not JSON, a body that breaks a rule: each costs that phrasing and nothing else, and the client shows
its template. Citations come from retrieval and are returned whatever the model did.
"""

import asyncio
import hashlib
import json
import logging
from typing import Any

import httpx

from ..config import Settings
from ..guidance import Passage, citations_for
from ..guidance.cite import terrain_at
from ..models import AssessmentData, Citation, HazardDef, Lang, NarratedHazard, Narration, Route
from ..narration.guard import normalise, violations
from ..narration.prompt import PROMPT_VERSION, RESPONSE_SCHEMA, build_correction, build_messages, parse_bodies
from .http import USER_AGENT, CacheKey, DiskCache

log = logging.getLogger(__name__)

GRADE_WORDS = {
    "T1": "hiking",
    "T2": "mountain hiking",
    "T3": "difficult mountain hiking",
    "T4": "alpine hiking",
    "T5": "difficult alpine hiking",
    "T6": "very difficult alpine hiking",
}
# Enough for seven hazards in either language, with room for a reasoning trace that slips through.
MAX_TOKENS = 2000
# Low but not zero: the point is phrasing that reads naturally, not variety.
TEMPERATURE = 0.3


def _citation(passage: Passage) -> Citation:
    return Citation(id=passage.id, title=passage.title, publisher=passage.publisher, url=passage.url)


def _ground(route: Route, hazard: HazardDef) -> str:
    """The ground in words only. Given "T3", a model quotes "T3", and a digit is what the guard drops."""
    terrain = terrain_at(route, hazard)
    grade = terrain.grade if terrain else route.grade
    words = f"{GRADE_WORDS[grade]} on the SAC hiking scale"
    return f"{words}, with fixed cables" if terrain and terrain.cables else words


class LlmNarrator:
    def __init__(self, settings: Settings, cache: DiskCache, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.cache = cache
        self._transport = transport
        self._locks: dict[str, asyncio.Lock] = {}

    async def narrate(self, route: Route, assessment: AssessmentData, lang: Lang) -> Narration:
        grounded = [(hazard, citations_for(route, hazard)) for hazard in assessment.hazards]
        enabled = self.settings.narration_configured
        bodies: dict[str, str] = {}
        if enabled and grounded:
            bodies = await self._bodies(route, grounded, lang)
        return Narration(
            enabled=enabled,
            model=self.settings.narration_model if enabled else None,
            hazards=[
                NarratedHazard(id=hazard.id, body=bodies.get(hazard.id), citations=[_citation(p) for p in citations])
                for hazard, citations in grounded
            ],
        )

    async def _bodies(
        self, route: Route, grounded: list[tuple[HazardDef, list[Passage]]], lang: Lang
    ) -> dict[str, str]:
        hazards = [hazard for hazard, _ in grounded]
        digest = hashlib.sha256(
            json.dumps([h.model_dump(mode="json") for h in hazards], sort_keys=True).encode()
        ).hexdigest()[:24]
        key = CacheKey(
            source="narration",
            endpoint="chat",
            model_run=self.settings.narration_model,
            params={"route": route.id, "lang": lang, "hazards": digest, "v": PROMPT_VERSION},
        )
        # One request per assessment and language, even when the web app and an agent ask at once.
        async with self._locks.setdefault(key.digest(), asyncio.Lock()):
            if (cached := self.cache.read(key, self.settings.cache_ttl_narration_s)) is not None:
                return cached

            messages = build_messages(
                [(hazard, _ground(route, hazard), citations) for hazard, citations in grounded],
                lang,
                self.settings.narration_thinking,
            )
            content = await self._complete(messages)
            accepted, rejected = self._check(content, hazards, lang)
            if rejected and content is not None:
                # One more turn, told exactly which rule each body broke. Its answers face the same guard.
                follow_up = [
                    *messages,
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": build_correction(rejected)},
                ]
                retried = [hazard for hazard in hazards if hazard.id in rejected]
                fixed, still = self._check(await self._complete(follow_up), retried, lang)
                accepted |= fixed
                log.info("narration: corrected %d of %d rejected bodies", len(fixed), len(rejected))
                for hazard_id, problems in still.items():
                    log.warning("narration for %s dropped: %s", hazard_id, "; ".join(problems))
            self.cache.write(key, accepted)
            return accepted

    @staticmethod
    def _check(
        content: str | None, hazards: list[HazardDef], lang: Lang
    ) -> tuple[dict[str, str], dict[str, list[str]]]:
        """Bodies that keep the rules, and for the rest why not. An unreadable answer is neither."""
        if content is None:
            return {}, {}
        try:
            answered = parse_bodies(content)
        except ValueError as exc:
            log.warning("narration answer unreadable (%s): %.200s", exc, content)
            return {}, {}

        accepted: dict[str, str] = {}
        rejected: dict[str, list[str]] = {}
        for hazard in hazards:
            if hazard.id not in answered:
                log.info("narration: no body for %s", hazard.id)
                continue
            body = normalise(answered[hazard.id])
            if problems := violations(body, hazard, lang):
                log.info("narration for %s rejected: %s: %r", hazard.id, "; ".join(problems), body)
                rejected[hazard.id] = problems
                continue
            accepted[hazard.id] = body
        return accepted, rejected

    async def _complete(self, messages: list[dict[str, str]]) -> str | None:
        """The model's answer, or None. Tries structured output first, then plain, then gives up."""
        settings = self.settings
        payload: dict[str, Any] = {
            "model": settings.narration_model,
            "messages": messages,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
        }
        extras: dict[str, Any] = {
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "narration", "schema": RESPONSE_SCHEMA, "strict": True},
            },
            # vLLM's switch for templates with a reasoning mode. Servers that do not know it may reject
            # the request, which is what the plain retry below is for.
            "chat_template_kwargs": {"enable_thinking": settings.narration_thinking},
        }
        headers = {"User-Agent": USER_AGENT}
        if settings.narration_api_key:
            headers["Authorization"] = f"Bearer {settings.narration_api_key}"
        url = f"{settings.narration_base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(
            timeout=settings.narration_timeout_s, transport=self._transport, headers=headers
        ) as client:
            body = payload | extras
            retried = False
            # At most: structured, then plain, then plain once more after a transient failure.
            for _ in range(3):
                try:
                    response = await client.post(url, json=body)
                except httpx.TransportError as exc:
                    log.warning("narration request failed: %s", exc)
                    if retried:
                        return None
                    retried = True
                    continue
                if response.status_code in (400, 422) and body is not payload:
                    # The server rejects an extra it does not support: ask plainly instead.
                    log.info("narration endpoint rejected structured output (HTTP %s)", response.status_code)
                    body = payload
                    continue
                if response.status_code >= 500 and not retried:
                    retried = True
                    continue
                if response.status_code >= 400:
                    log.warning("narration endpoint answered HTTP %s: %.200s", response.status_code, response.text)
                    return None
                try:
                    return response.json()["choices"][0]["message"]["content"] or None
                except (ValueError, KeyError, IndexError, TypeError):
                    log.warning("narration endpoint answered an unexpected body: %.200s", response.text)
                    return None
        return None
