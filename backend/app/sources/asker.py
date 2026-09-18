"""The live `Asker`: a hiker's question, answered by a language model from the briefing, behind the rules.

Like narration, nothing here can break the app. No endpoint, a timeout, an unreadable answer: the reason
says so and the client shows a fixed sentence. An answer that breaks a rule is sent back once with the
rules it broke; if the rewrite breaks one too, nothing is shown.
"""

import asyncio
import hashlib
import json
import logging
import re
from datetime import date

import httpx

from ..ask import ASK_PROMPT_VERSION, build_briefing, build_correction, build_messages, fill, parse_answer, violations
from ..ask.guard import normalise, strip_echoes
from ..ask.prompt import RESPONSE_SCHEMA
from ..config import Settings
from ..guidance import Passage, citations_for, search
from ..models import Answer, AskRequest, AssessmentData, Citation, Lang, Route
from . import chat
from .http import CacheKey, DiskCache

log = logging.getLogger(__name__)

MAX_TOKENS = 1200
TEMPERATURE = 0.3
# Retrieved for the question itself, then one per flagged hazard, capped.
QUESTION_PASSAGES = 3
MAX_PASSAGES = 6


# Someone hurt, lost or in danger, in either language. Deliberately broad: a false positive costs one
# sentence telling the hiker the emergency number, a false negative leaves them with "off topic".
EMERGENCY = re.compile(
    r"\b(hurt|injur\w*|twist\w*|sprain\w*|broke\w*|bleed\w*|fell|fallen|falling|lost|unconscious|accident|"
    r"emergency|rescue|help|sick|faint\w*|stuck|bless[ée]\w*|perdu\w*|urgence|secours|tomb[ée]\w*|malaise|"
    r"coinc[ée]\w*|entors\w*|saign\w*|aide)\b",
    re.IGNORECASE,
)
EMERGENCY_TEXT: dict[Lang, str] = {
    "en": "If anyone is hurt, lost or in danger, call {emergency} now. The bail-out on this route is {bailout}.",
    "fr": "Si quelqu'un est blessé, perdu ou en danger, appelez le {emergency} maintenant. "
    "La sortie de secours sur cet itinéraire est {bailout}.",
}


def emergency_answer(route: Route, facts: dict[str, str], lang: Lang, model: str) -> Answer:
    text = EMERGENCY_TEXT[lang].format(emergency=facts["emergency"], bailout=route.bailout_name)
    return Answer(enabled=True, model=model, reason="emergency", text=text, citations=[])


def _citation(passage: Passage) -> Citation:
    return Citation(id=passage.id, title=passage.title, publisher=passage.publisher, url=passage.url)


def passages_for(route: Route, assessment: AssessmentData, question: str) -> list[Passage]:
    found: dict[str, Passage] = {}
    for passage in search(question, grade=route.grade, k=QUESTION_PASSAGES):
        found.setdefault(passage.id, passage)
    for hazard in assessment.hazards:
        for passage in citations_for(route, hazard, k=1):
            found.setdefault(passage.id, passage)
    return list(found.values())[:MAX_PASSAGES]


class LlmAsker:
    def __init__(self, settings: Settings, cache: DiskCache, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.cache = cache
        self._transport = transport
        self._locks: dict[str, asyncio.Lock] = {}

    async def ask(self, route: Route, assessment: AssessmentData, request: AskRequest, day: date, lang: Lang) -> Answer:
        if not self.settings.narration_configured:
            return Answer(enabled=False, reason="disabled", citations=[])
        briefing = build_briefing(route, assessment, day, request.plan, request.live)
        passages = passages_for(route, assessment, request.question)
        # A question asked during a hike is about this minute: never answered from the cache.
        key = None if request.live is not None else self._key(route, day, lang, request, briefing.text)
        if key is None:
            answer = await self._answer(briefing, passages, request, lang)
        else:
            async with self._locks.setdefault(key.digest(), asyncio.Lock()):
                if (cached := self.cache.read(key, self.settings.cache_ttl_narration_s)) is not None:
                    return Answer.model_validate(cached)
                answer = await self._answer(briefing, passages, request, lang)
                # A dropped answer may well be kept by the next try: only a real answer is worth keeping.
                if answer.reason not in ("unavailable", "dropped"):
                    self.cache.write(key, answer.model_dump(mode="json", by_alias=True, exclude_none=True))
        # Never "off topic" or silence for someone hurt or lost: the app's own sentence instead.
        if answer.reason != "ok" and EMERGENCY.search(request.question):
            return emergency_answer(route, briefing.facts, lang, self.settings.narration_model)
        return answer

    def _key(self, route: Route, day: date, lang: Lang, request: AskRequest, briefing: str) -> CacheKey:
        conversation = [turn.model_dump(mode="json") for turn in request.history]
        digest = hashlib.sha256(
            json.dumps([" ".join(request.question.casefold().split()), conversation, briefing]).encode()
        ).hexdigest()[:24]
        return CacheKey(
            source="ask",
            endpoint="chat",
            model_run=self.settings.narration_model,
            params={"route": route.id, "day": day.isoformat(), "lang": lang, "q": digest, "v": ASK_PROMPT_VERSION},
        )

    async def _answer(self, briefing, passages: list[Passage], request: AskRequest, lang: Lang) -> Answer:
        model = self.settings.narration_model
        offered = {p.id for p in passages}
        messages = build_messages(
            briefing, passages, request.question, request.history, lang, self.settings.narration_thinking
        )

        content = await self._complete(messages)
        for attempt in range(2):
            if content is None:
                return Answer(enabled=True, model=model, reason="unavailable", citations=[])
            try:
                text, reason, cited = parse_answer(content)
            except ValueError as exc:
                log.warning("ask: answer unreadable (%s): %.200s", exc, content)
                return Answer(enabled=True, model=model, reason="unavailable", citations=[])
            if reason == "off_topic" or text is None:
                return Answer(enabled=True, model=model, reason="off_topic", citations=[])
            text = strip_echoes(normalise_lines(text), briefing.facts)
            problems = violations(text, briefing.facts, lang)
            if not problems:
                # Ids it was not given (a hazard id, say) are ignored rather than held against the answer.
                used = [p for p in passages if p.id in set(cited) & offered]
                return Answer(
                    enabled=True,
                    model=model,
                    reason="ok",
                    text=fill(text, briefing.facts),
                    citations=[_citation(p) for p in used],
                )
            log.warning("ask: answer rejected (attempt %d): %s: %r", attempt + 1, "; ".join(problems), text)
            if attempt == 0:
                follow_up = [*messages, {"role": "assistant", "content": content}]
                follow_up.append({"role": "user", "content": build_correction(problems)})
                content = await self._complete(follow_up)
        log.warning("ask: answer dropped after a correction")
        return Answer(enabled=True, model=model, reason="dropped", citations=[])

    async def _complete(self, messages: list[dict[str, str]]) -> str | None:
        return await chat.complete(
            self.settings,
            messages,
            schema_name="answer",
            schema=RESPONSE_SCHEMA,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            transport=self._transport,
        )


def normalise_lines(text: str) -> str:
    """Tidy spacing but keep the line breaks a short list needs."""
    lines = [normalise(line) for line in text.strip().splitlines()]
    return "\n".join(line for line in lines if line)
