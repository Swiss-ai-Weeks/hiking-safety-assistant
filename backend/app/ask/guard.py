"""The rules an answer must keep before anyone sees it, and filling in its figures afterwards.

The same idea as `narration/guard.py`, for longer text with more figures. The guarantee is that no
figure in an answer is one the model made up: every number must be one the briefing gave, with the
same unit. The model is asked to write placeholders, which the server fills; a number it copied from
the briefing verbatim (`11:00`, `60 km/h`) is the same figure and passes too. Anything else with a digit
is refused, and so is verdict wording. Nothing is repaired.
"""

import re

from ..models import Lang
from ..narration.guard import BANNED, GENERATED_BANNED, normalise

MAX_CHARS = 700

PLACEHOLDER = re.compile(r"\{([A-Za-z][\w.\-]*)\}")
# A number as the briefing writes one: `-2`, `1.2`, `10:40`, and the French clock `10h40`.
NUMBER = re.compile(r"(?<![\w.:])-?\d+(?:[.:h]\d+)?(?![\w.:]*\d)")
UNITS = ("km/h", "mm/h", "km", "°C", "%", "min", "m", "h")
_UNIT_AFTER = re.compile(r"\s*(km/h|mm/h|km|°C|%|min|m|h)(?![A-Za-zÀ-ÿ])")
_FRENCH_CLOCK = re.compile(r"^(\d{1,2})h(\d{2})$")
# `1 304 m`, `1'304 m`: a height copied with its thousands grouped. Joined again only when the joined
# figure is one the briefing gave, so two separate numbers are never read as one.
_GROUPED = re.compile(r"(?<![\w.:])\d{1,3}(?:[   '’]\d{3})+(?![\w.:]*\d)")

__all__ = ["MAX_CHARS", "PLACEHOLDER", "allowed_figures", "fill", "normalise", "strip_echoes", "violations"]


def _figure(number: str) -> str:
    """One spelling per figure: `9h05` and `09:05` are the same clock time."""
    if match := _FRENCH_CLOCK.match(number):
        number = f"{match.group(1)}:{match.group(2)}"
    if ":" in number:
        hours, minutes = number.split(":")
        return f"{int(hours):02d}:{minutes}"
    return number


def allowed_figures(facts: dict[str, str]) -> set[tuple[str, str]]:
    """Every (number, unit) the briefing gave. A clock time has no unit."""
    allowed: set[tuple[str, str]] = set()
    for value in facts.values():
        for match in NUMBER.finditer(value):
            unit = _UNIT_AFTER.match(value, match.end())
            allowed.add((_figure(match.group()), unit.group(1) if unit else ""))
    return allowed


def strip_echoes(text: str, facts: dict[str, str]) -> str:
    """`{eta} = 10:40` -> `{eta}`: the model copying the briefing's own notation, however often."""
    out: list[str] = []
    position = 0
    for match in re.finditer(r"\{([A-Za-z][\w.\-]*)\}(\s*=\s*)", text):
        value = facts.get(match.group(1))
        if match.start() < position or value is None or not text.startswith(value, match.end()):
            continue
        out.append(text[position : match.start()] + "{" + match.group(1) + "}")
        position = match.end() + len(value)
    out.append(text[position:])
    return "".join(out)


def _ungroup(text: str, allowed: set[tuple[str, str]]) -> str:
    def join(match: re.Match[str]) -> str:
        joined = re.sub(r"\D", "", match.group())
        unit = _UNIT_AFTER.match(text, match.end())
        return joined if (joined, unit.group(1) if unit else "") in allowed else match.group()

    return _GROUPED.sub(join, text)


def violations(text: str, facts: dict[str, str], lang: Lang) -> list[str]:
    """Why `text` may not be shown. Empty when it may."""
    found: list[str] = []
    if not text.strip():
        return ["empty"]
    if len(text) > MAX_CHARS:
        found.append(f"longer than {MAX_CHARS} characters")
    allowed = allowed_figures(facts)
    bare = _ungroup(PLACEHOLDER.sub("", text), allowed)
    invented = []
    for match in NUMBER.finditer(bare):
        unit = _UNIT_AFTER.match(bare, match.end())
        figure = (_figure(match.group()), unit.group(1) if unit else "")
        if figure not in allowed:
            invented.append("".join(filter(None, figure)))
    if invented:
        found.append(f"figures not in the briefing: {', '.join(invented)}")
    elif re.search(r"\d", NUMBER.sub("", bare)):
        found.append("a digit outside any figure")
    unknown = sorted({name for name in PLACEHOLDER.findall(text) if name not in facts})
    if unknown:
        found.append("placeholders not in the briefing: " + ", ".join(f"{{{name}}}" for name in unknown))
    if "{" in bare or "}" in bare:
        found.append("stray brace")
    for pattern in BANNED[lang] + GENERATED_BANNED[lang]:
        if pattern.search(text):
            found.append(f"verdict wording /{pattern.pattern}/")
    return found


def fill(text: str, facts: dict[str, str]) -> str:
    return PLACEHOLDER.sub(lambda match: facts[match.group(1)], text)
