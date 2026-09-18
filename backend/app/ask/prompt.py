"""The conversation a question becomes, and reading the answer back."""

import json
import re
from typing import Any

from ..guidance import Passage
from ..models import AskTurn, Lang
from .briefing import Briefing
from .guard import MAX_CHARS

# Part of the cache key: bump it whenever the prompt or the answer format changes.
ASK_PROMPT_VERSION = 5

LANGUAGE: dict[Lang, str] = {"en": "English (British spelling)", "fr": "French (as written in Switzerland, vous)"}

SYSTEM = """You are Nemotron, answering a hiker's questions inside a Swiss mountain hiking safety app.

The BRIEFING below is everything known about this hike: the route, the hiker's plan and, during a hike,
where they are now. A rules engine has already decided every hazard, time and severity in it, and the
turnaround rule is the hiker's own. You decide nothing. You explain what the briefing says, and use the
GUIDANCE passages for why it matters.

Rules, all strict:
1. Write in {language}, to the hiker as "you". Calm and plain, for a phone. At most {max_chars}
   characters. Short sentences; up to four short lines starting with "- " when a list helps.
2. Every figure (time, distance, height, speed, temperature, percentage) must come from the briefing.
   Write it as its placeholder, exactly, braces included, e.g. "you reach Hohtürli about {{eta}}" or
   "gusts to {{h.gusts-hohturli.gust}}". Write the placeholder alone: its value already has its unit,
   and never repeat the "= value" part. A figure belongs to the place and time the briefing gives it
   for: never move it to another stop or hour. Never calculate a new figure (no sums, differences or
   shifted times); describe the change in words instead. For another start time, quote the IF YOU
   START LATER or Alternative lines; never shift a time yourself. Write SAC grades in words.
3. Use only the BRIEFING and the GUIDANCE. If they do not answer the question, say so in one sentence
   and say what they do tell. Never guess or invent weather, places, times or advice.
4. Never tell the hiker whether to go, carry on or turn back, and never call anything safe, fine,
   risk-free or harmless. Asked "should I go", summarise for them: which hazards are flagged, where and
   when; what was not evaluated; the gaps; the alternatives; and their own turnaround rule. If the
   briefing says their own rule says turn, say plainly that their rule says to turn back and descend
   via the bail-out.
5. Injuries, feeling unwell, being lost, bad weather arriving, or any emergency: start with the
   emergency number placeholder, then name only what the briefing gives (the bail-out, the nearest
   stops). Give no first-aid or rescue advice of your own. Keep it to two or three sentences.
6. Keep place names exactly as written; never translate them.
7. Only if the question has nothing to do with this hike, hiking, the mountains, the weather or safety,
   answer null with reason "off_topic". Always on topic: injuries, feeling unwell, being lost, what to
   carry, shelter. Off topic: creative writing, sport, general knowledge. Answer only the question
   asked; never add another question or example of your own.
8. Answer with JSON only:
   {{"answer": "<text or null>", "reason": "ok" or "off_topic", "passageIds": ["<guidance ids you used>"]}}"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": ["string", "null"]},
        "reason": {"type": "string", "enum": ["ok", "off_topic"]},
        "passageIds": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "reason", "passageIds"],
    "additionalProperties": False,
}


def build_messages(
    briefing: Briefing,
    passages: list[Passage],
    question: str,
    history: list[AskTurn],
    lang: Lang,
    thinking: bool,
) -> list[dict[str, str]]:
    system = SYSTEM.format(language=LANGUAGE[lang], max_chars=MAX_CHARS)
    if not thinking:
        system = "/no_think\n" + system
    guidance = "\n\n".join(f"[{p.id}] {p.publisher}, {p.title}:\n{p.text}" for p in passages) or "(none found)"
    context = f"BRIEFING\n\n{briefing.text}\n\nGUIDANCE PASSAGES\n\n{guidance}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": context}]
    messages.append({"role": "assistant", "content": '{"answer": "Understood.", "reason": "ok", "passageIds": []}'})
    for turn in history:
        # Earlier answers are shown as the hiker saw them, figures filled in. Said so, so the model does
        # not copy their digits.
        messages.append({"role": "user", "content": f"QUESTION: {turn.question}"})
        messages.append({"role": "assistant", "content": f"(shown to the hiker with figures filled in) {turn.answer}"})
    messages.append({"role": "user", "content": f"QUESTION: {question}"})
    return messages


def build_correction(problems: list[str]) -> str:
    return (
        "That answer broke the rules and will not be shown: "
        + "; ".join(problems)
        + ". Answer the same question again in the same JSON format, keeping every rule: no digit at all, "
        "only placeholders that appear in the briefing, no verdict."
    )


_THINK = re.compile(r"<think>.*?(</think>|$)", re.DOTALL)


def parse_answer(content: str) -> tuple[str | None, str, list[str]]:
    """(answer, reason, passage ids). Raises `ValueError` if the content is not the JSON asked for."""
    text = _THINK.sub("", content)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in the answer")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("answer is not an object")
    answer = data.get("answer")
    if answer is not None and not isinstance(answer, str):
        raise ValueError("`answer` is neither text nor null")
    reason = "off_topic" if data.get("reason") == "off_topic" or answer is None else "ok"
    ids = data.get("passageIds")
    passage_ids = [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []
    return answer, reason, passage_ids
