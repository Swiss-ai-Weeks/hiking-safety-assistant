"""The copy rules, applied to text a model wrote.

The verdict patterns are `BANNED` in `frontend/src/i18n/copyRules.ts`, translated to Python's `re`
(which has no `\\p{L}`: `[^\\W\\d_]` is a letter). `GENERATED_BANNED` is the stricter list only
generated text is held to, because a template is reviewed once and a model writes something new
every time. The client applies both again before it shows a body.
"""

import re

from ..models import HazardDef, Lang
from .placeholders import BASE_PLACEHOLDERS, FACT_PLACEHOLDERS, available

MAX_CHARS = 320

_LETTER = r"[^\W\d_]"

BANNED: dict[Lang, list[re.Pattern[str]]] = {
    "en": [
        re.compile(p, re.IGNORECASE)
        for p in (r"\bsafe(ly)?\b", r"\bfine\b", r"\bclear to\b", r"\bgood to go\b", r"\bgo ahead\b")
    ],
    "fr": [
        re.compile(p, re.IGNORECASE)
        for p in (rf"(?<!{_LETTER})sûre?s?(?!{_LETTER})", r"sans danger", r"en sécurité", r"vous pouvez y aller")
    ],
}

GENERATED_BANNED: dict[Lang, list[re.Pattern[str]]] = {
    "en": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\bno (real )?(risk|danger|hazard)s?\b",
            r"\brisk[- ]free\b",
            r"\bnot dangerous\b",
            r"\bnothing to worry\b",
            r"\bguarantee",
            r"\b(do not|don't|should not|shouldn't) (go|hike|attempt)\b",
        )
    ],
    "fr": [
        re.compile(p, re.IGNORECASE)
        for p in (
            r"sans risque",
            r"aucun (risque|danger)",
            r"pas dangereu",
            r"garanti",
            r"(n'|ne )(allez|partez|tentez) pas",
        )
    ],
}

_DIGIT = re.compile(r"\d")
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def normalise(text: str) -> str:
    """One line, single spaces: what the card renders anyway."""
    return " ".join(text.split())


def violations(text: str, hazard: HazardDef, lang: Lang) -> list[str]:
    """Why `text` may not be shown as the body of `hazard`. Empty when it may."""
    found: list[str] = []
    if not text:
        return ["empty"]
    if len(text) > MAX_CHARS:
        found.append(f"longer than {MAX_CHARS} characters")
    if digits := sorted(set(_DIGIT.findall(text))):
        found.append(f"contains a figure ({''.join(digits)}): numbers come only from the facts")

    fillable = available(hazard)
    known = set(BASE_PLACEHOLDERS) | set(FACT_PLACEHOLDERS)
    for name in _PLACEHOLDER.findall(text):
        if name not in known:
            found.append(f"unknown placeholder {{{name}}}")
        elif name not in fillable:
            found.append(f"placeholder {{{name}}} has no value for this hazard")
    if "{" in _PLACEHOLDER.sub("", text) or "}" in _PLACEHOLDER.sub("", text):
        found.append("stray brace")

    for pattern in BANNED[lang] + GENERATED_BANNED[lang]:
        if pattern.search(text):
            found.append(f"verdict wording /{pattern.pattern}/")
    return found
