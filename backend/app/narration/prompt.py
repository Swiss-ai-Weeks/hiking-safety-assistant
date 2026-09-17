"""The request a model is sent, and reading its answer back.

One request covers every hazard of an assessment in one language. The prompt carries what the
engine decided (kind, place, window, ground), the placeholders with their values for context, and
the guidance passages retrieved for each hazard. The model's only job is the sentence.
"""

import json
import re
from typing import Any

from ..guidance import Passage
from ..models import HazardDef, Lang
from .guard import MAX_CHARS
from .placeholders import UNIT_HINTS, available

# Bumped whenever the prompt or the answer format changes: it is part of the cache key.
PROMPT_VERSION = 1

LANGUAGE: dict[Lang, str] = {"en": "English (British spelling)", "fr": "French (as written in Switzerland, vous)"}

KIND_NAMES = {
    "gusts": "strong wind gusts",
    "showers": "showers and wet rock",
    "thunder": "thunderstorm potential",
    "cold": "wind chill below freezing",
    "snow": "snow or ice on the route",
    "visibility": "cloud down on the route",
    "daylight": "darkness before the hike ends",
}

SYSTEM = """You write one short explanation per hazard for a Swiss mountain hiking app.

A rules engine has already decided every hazard: what it is, where, when and how severe. You decide
nothing. You explain, for a hiker reading on a phone, why this hazard matters on this ground, using
only the hazard data and the guidance passages given.

Rules, all of them strict:
1. Write in {language}. One or two sentences, at most {max_chars} characters.
2. Never write a digit, not even in a grade name such as T3: describe the ground in words.
3. To quote a figure, write its placeholder exactly as listed, in braces, e.g. {{gust}} km/h. Use
   only the placeholders listed for that hazard. Leave figures out rather than guess one.
4. Never give a verdict or permission. Do not say or imply that anything is safe, fine, risk-free
   or fine to go ahead with, and do not tell the hiker whether to do the hike.
5. Add no facts, places or advice that are not in the hazard data or the passages.
6. Keep place names exactly as given; never translate them.
7. Answer with JSON only, no prose around it: {{"hazards": [{{"id": "<hazard id>", "body": "<text>"}}]}}"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "hazards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "body": {"type": "string"}},
                "required": ["id", "body"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["hazards"],
    "additionalProperties": False,
}


def _describe(hazard: HazardDef, ground: str, citations: list[Passage]) -> str:
    lines = [
        f"id: {hazard.id}",
        f"hazard: {KIND_NAMES[hazard.kind]}",
        f"ground where it is worst: {ground}",
        "placeholders you may use (the value is for your understanding; write the placeholder):",
    ]
    for name, value in available(hazard).items():
        lines.append(f"  {{{name}}} = {value} — {UNIT_HINTS[name]}")
    lines.append(f"guidance: {', '.join(p.id for p in citations) or 'none'}")
    return "\n".join(lines)


def build_messages(
    hazards: list[tuple[HazardDef, str, list[Passage]]], lang: Lang, thinking: bool
) -> list[dict[str, str]]:
    """`hazards` pairs each hazard with a description of its ground and the passages that ground it."""
    system = SYSTEM.format(language=LANGUAGE[lang], max_chars=MAX_CHARS)
    if not thinking:
        # Nemotron's switch for its reasoning trace. Other models read it as a harmless line.
        system = "/no_think\n" + system

    passages: dict[str, Passage] = {}
    for _, _, citations in hazards:
        passages.update((p.id, p) for p in citations)
    guidance = "\n\n".join(f"[{p.id}] {p.publisher}, {p.title}:\n{p.text}" for p in passages.values())
    described = "\n\n".join(_describe(hazard, ground, citations) for hazard, ground, citations in hazards)
    user = f"GUIDANCE PASSAGES\n\n{guidance}\n\nHAZARDS\n\n{described}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


_THINK = re.compile(r"<think>.*?(</think>|$)", re.DOTALL)


def parse_bodies(content: str) -> dict[str, str]:
    """Hazard id -> body, from whatever the model answered. Raises `ValueError` if it is not the JSON asked for.

    Reasoning traces and code fences are tolerated, because some servers pass them through even when
    a JSON format was requested.
    """
    text = _THINK.sub("", content)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in the answer")
    data = json.loads(text[start : end + 1])
    rows = data.get("hazards") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("answer has no `hazards` list")
    return {
        row["id"]: row["body"]
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str) and isinstance(row.get("body"), str)
    }
