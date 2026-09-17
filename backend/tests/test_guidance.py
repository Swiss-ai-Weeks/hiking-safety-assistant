"""The curated corpus, retrieval over it, and the citation each hazard gets."""

import re
from typing import get_args

import pytest

from app.guidance import citations_for, load_corpus, search
from app.guidance.cite import KIND_QUERY
from app.guidance.corpus import parse_passage
from app.mock_data import HAZARDS, OESCHINEN_ROUTE
from app.models import Grade, HazardKind

CORPUS = load_corpus()


def test_every_passage_names_its_source():
    assert len(CORPUS) >= 15
    for passage in CORPUS:
        assert passage.url.startswith("https://"), passage.id
        assert passage.publisher and passage.title and passage.cite, passage.id
        assert passage.kinds <= set(get_args(HazardKind)), passage.id
        assert passage.grades and passage.grades <= set(get_args(Grade)), passage.id


def test_passages_carry_no_figures():
    # Narration may not write a digit; a passage full of them only invites one.
    assert [p.id for p in CORPUS if re.search(r"\d", p.text)] == []


def test_a_passage_missing_a_field_is_refused():
    with pytest.raises(ValueError, match="missing cite"):
        parse_passage("x", "---\ntitle: t\npublisher: p\nurl: u\nkinds: gusts\ngrades: T1\n---\ntext")


@pytest.mark.parametrize("kind", get_args(HazardKind))
@pytest.mark.parametrize("grade", get_args(Grade))
def test_every_hazard_on_every_grade_is_grounded_in_a_passage_about_it(kind, grade):
    cited = search(KIND_QUERY[kind], kind=kind, grade=grade, k=2)

    assert len(cited) == 2
    assert kind in cited[0].kinds


def test_exposed_gusts_cite_the_grade_of_the_ground():
    assert search(KIND_QUERY["gusts"], kind="gusts", grade="T3")[0].id == "sac-scale-difficult-mountain-hiking"
    assert search(KIND_QUERY["gusts"], kind="gusts", grade="T4")[0].id == "sac-scale-alpine-hiking"


def test_thunder_cites_where_lightning_strikes():
    assert search(KIND_QUERY["thunder"], kind="thunder", grade="T3")[0].id == "rando-lightning-exposure"


def test_citations_for_the_demo_hazards_follow_the_ground_at_their_worst_stop():
    gusts, showers = HAZARDS

    assert [p.id for p in citations_for(OESCHINEN_ROUTE, gusts)] == [
        "sac-scale-difficult-mountain-hiking",
        "sac-weather-planning",
    ]
    assert citations_for(OESCHINEN_ROUTE, showers)[0].id == "wet-rock"


def test_retrieval_is_deterministic_and_never_returns_the_unrelated():
    assert search("lightning ridge") == search("lightning ridge")
    assert search("zzzz qqqq") == []
