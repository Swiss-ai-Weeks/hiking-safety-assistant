"""The copy rules for generated text, the placeholder contract with the client, and the prompt."""

import re
from pathlib import Path

import pytest
from authored import HAZARDS, OESCHINEN_ROUTE

from app.guidance import citations_for
from app.models import HazardDef, HazardFacts, Window
from app.narration.guard import normalise, violations
from app.narration.placeholders import FACT_PLACEHOLDERS, available
from app.narration.prompt import build_messages, parse_bodies

HAZARD_COPY_TS = Path(__file__).parents[2] / "frontend" / "src" / "i18n" / "hazardCopy.ts"

GUSTS, SHOWERS = HAZARDS


def test_placeholders_match_the_client_that_fills_them():
    ts = HAZARD_COPY_TS.read_text(encoding="utf-8")
    client = dict(re.findall(r"^\s+(\w+): \{ fact: '(\w+)'", ts, flags=re.MULTILINE))
    camel = {name: re.sub(r"_(\w)", lambda m: m[1].upper(), field) for name, field in FACT_PLACEHOLDERS.items()}

    assert client == camel


def test_available_placeholders_are_the_ones_with_values():
    assert available(GUSTS) == {
        "from": "11:00",
        "to": "14:00",
        "place": "Hohtürli",
        "gust": "60",
        "threshold": "40",
        "elevation": "2778",
    }
    # No place on the showers hazard, so `{place}` is not offered.
    assert "place" not in available(SHOWERS)


def test_a_body_quoting_facts_by_placeholder_passes():
    text = "Gusts of {gust} km/h at {place} from {from}: on ground where hands are needed, balance goes first."
    assert violations(text, GUSTS, "en") == []


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("Gusts of 60 km/h at {place}.", "contains a figure"),
        ("Gusts at {place} on T3 ground.", "contains a figure"),
        ("Gusts of {speed} km/h.", "unknown placeholder {speed}"),
        ("Rain up to {precip} mm near {place}.", "placeholder {place} has no value"),
        ("Gusts at {place {gust}.", "stray brace"),
        ("The col is safe after {to}.", "verdict wording"),
        ("Fine for a steady hiker after {to}.", "verdict wording"),
        ("There is no real risk at {place}.", "verdict wording"),
        ("You should not go past {place}.", "verdict wording"),
        ("", "empty"),
        ("x" * 400, "longer than"),
    ],
)
def test_bodies_that_break_a_rule_are_refused(text, problem):
    hazard = SHOWERS if "{precip}" in text else GUSTS
    assert any(problem in found for found in violations(text, hazard, "en"))


@pytest.mark.parametrize(
    "text",
    [
        "Le passage est sûr après {to}.",
        "Montée sans danger à {place}.",
        "Aucun risque à {place}.",
        "N'allez pas au {place}.",
    ],
)
def test_french_verdicts_are_refused(text):
    assert any("verdict" in found for found in violations(text, GUSTS, "fr"))


def test_french_letters_around_the_banned_word_do_not_count():
    # "assurez" contains "sûr" only without its accent, and "mesure" not as a word.
    assert violations("Assurez vos prises au {place}, la mesure du vent compte.", GUSTS, "fr") == []


def test_whitespace_is_normalised_before_checking():
    assert normalise("  Gusts\nat {place}.  ") == "Gusts at {place}."


def test_prompt_lists_each_hazard_with_its_placeholders_and_passages():
    ground = "T3 on the SAC scale (difficult mountain hiking)"
    grounded = [(h, ground, citations_for(OESCHINEN_ROUTE, h)) for h in HAZARDS]
    system, user = build_messages(grounded, "fr", thinking=False)

    assert system["content"].startswith("/no_think\n")
    assert "French" in system["content"]
    assert "{gust} = 60" in user["content"]
    assert "[sac-scale-difficult-mountain-hiking] Swiss Alpine Club SAC" in user["content"]
    assert "{place}" not in user["content"].split("id: showers-descent")[1]


def test_prompt_keeps_the_reasoning_trace_when_asked():
    system, _ = build_messages([(GUSTS, "T3", [])], "en", thinking=True)
    assert not system["content"].startswith("/no_think")


def test_answers_are_read_through_reasoning_and_fences():
    content = '<think>the col is exposed</think>\n```json\n{"hazards": [{"id": "a", "body": "x"}, {"id": 3}]}\n```'
    assert parse_bodies(content) == {"a": "x"}


@pytest.mark.parametrize("content", ["no json here", '{"items": []}', "{not json}"])
def test_unreadable_answers_raise(content):
    with pytest.raises(ValueError):
        parse_bodies(content)


def test_a_hazard_without_facts_offers_only_its_window():
    bare = HazardDef(
        id="snow-x", kind="snow", window=Window(from_=600, to=660), stops={}, has_lifts_if=False, provenance="p"
    )
    assert available(bare) == {"from": "10:00", "to": "11:00"}
    # Clock facts are offered as the clock the client will show.
    assert available(bare.model_copy(update={"facts": HazardFacts(sunset=1175)}))["sunset"] == "19:35"
