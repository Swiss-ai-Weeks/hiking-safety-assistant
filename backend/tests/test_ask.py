"""Asking about a hike: the briefing's figures, the guard, and the asker over a scripted model endpoint."""

import json
from datetime import date

import httpx
import pytest
from authored import OESCHINEN_ROUTE, authored_sources, get_assessment
from fastapi.testclient import TestClient

from app import api
from app.ask import build_briefing, fill, parse_answer, violations
from app.ask.guard import strip_echoes
from app.config import Settings, get_settings
from app.main import create_app
from app.models import AskRequest, AskTurn, LiveContext, PlanContext
from app.sources import get_sources
from app.sources.asker import LlmAsker, passages_for
from app.sources.http import DiskCache

pytestmark = pytest.mark.anyio

DAY = date(2026, 9, 18)
ASSESSED = get_assessment("assessed")
ARRIVALS = {stop.id: 450 + i * 60 for i, stop in enumerate(OESCHINEN_ROUTE.stops)}
PLAN = PlanContext(start=450, turnaround=660, arrivals=ARRIVALS)


def live(**overrides) -> LiveContext:
    fields = {
        "now": 600,
        "status": "ahead",
        "next_stop_id": OESCHINEN_ROUTE.crux_stop_id,
        "eta": 640,
        "remaining_km": 2.1,
        "remaining_ascent_m": 520,
    }
    return LiveContext(**(fields | overrides))


# The briefing


def test_every_figure_in_the_briefing_is_a_placeholder_with_its_unit():
    briefing = build_briefing(OESCHINEN_ROUTE, ASSESSED, DAY, PLAN, live())

    assert briefing.facts["h.gusts-hohturli.gust"] == "60 km/h"
    assert briefing.facts["arrive.hohturli"] == "10:30"
    assert briefing.facts["wx.hutte.gust"] == "55 km/h"
    assert briefing.facts["turnBy"] == "11:00"
    assert briefing.facts["eta"] == "10:40"
    assert briefing.facts["emergency"] == "1414 (Rega)"
    for name, value in briefing.facts.items():
        assert f"{{{name}}} = {value}" in briefing.text


def test_without_a_plan_or_a_hike_there_are_no_arrival_or_live_figures():
    briefing = build_briefing(OESCHINEN_ROUTE, ASSESSED, DAY)

    assert not any(name.startswith(("arrive.", "wx.", "now", "eta")) for name in briefing.facts)
    assert briefing.facts["turnBy"] == "11:30", "the route default rule still applies"
    assert "RIGHT NOW" not in briefing.text


@pytest.mark.parametrize(("status", "cloud"), [("behind", None), ("ahead", "below")])
def test_the_hikers_own_rule_saying_turn_is_put_plainly(status, cloud):
    briefing = build_briefing(OESCHINEN_ROUTE, ASSESSED, DAY, PLAN, live(status=status, cloud=cloud))

    assert briefing.rule_says_turn
    assert "RULE SAYS TURN BACK NOW AND DESCEND VIA Oberbärgli" in briefing.text


def test_a_day_without_an_assessment_says_the_weather_is_unknown():
    briefing = build_briefing(OESCHINEN_ROUTE, get_assessment("not_assessable"), DAY)

    assert "Nothing is known about the weather" in briefing.text
    assert "h.gusts-hohturli.gust" not in briefing.facts


# The guard


FACTS = {"eta": "10:40", "h.gusts-hohturli.gust": "60 km/h"}


def test_an_answer_quoting_figures_only_through_placeholders_passes_and_is_filled():
    text = "You reach Hohtürli about {eta}. Gusts there reach {h.gusts-hohturli.gust}."

    assert violations(text, FACTS, "en") == []
    assert fill(text, FACTS) == "You reach Hohtürli about 10:40. Gusts there reach 60 km/h."


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("Gusts reach 70 km/h.", "figures not in the briefing: 70km/h"),
        ("Gusts reach 60 mm/h.", "figures not in the briefing"),
        ("You arrive at 10:45.", "figures not in the briefing: 10:45"),
        ("On the T3 section.", "digit outside"),
        ("You reach it at {arrival}.", "placeholders not in the briefing"),
        ("Gusts {gust.", "stray brace"),
        ("The pass is safe after {eta}.", "verdict"),
        ("There is no real risk.", "verdict"),
        ("Don't go.", "verdict"),
        ("x" * 701, "longer than"),
    ],
)
def test_an_answer_that_breaks_a_rule_is_refused(text, problem):
    assert any(problem in found for found in violations(text, FACTS, "en"))


def test_french_verdicts_are_refused_too():
    assert violations("Le passage est sans danger.", FACTS, "fr")


def test_a_figure_copied_from_the_briefing_is_the_same_figure_and_passes():
    assert violations("You reach Hohtürli about 10:40, gusts to 60 km/h, in French 10h40.", FACTS, "fr") == []


def test_the_briefings_own_notation_is_stripped_however_often_it_is_copied():
    text = "About {eta} = 10:40. Gusts {h.gusts-hohturli.gust} = 60 km/h, then {eta} = 10:40."

    assert strip_echoes(text, FACTS) == "About {eta}. Gusts {h.gusts-hohturli.gust}, then {eta}."


def test_the_answer_json_is_read_through_reasoning_and_fences():
    content = '<think>hmm</think>```json\n{"answer": "Hi {eta}", "reason": "ok", "passageIds": ["a", 3]}\n```'

    assert parse_answer(content) == ("Hi {eta}", "ok", ["a"])
    assert parse_answer('{"answer": null, "reason": "ok", "passageIds": []}')[1] == "off_topic"
    with pytest.raises(ValueError):
        parse_answer("I cannot answer")


def test_passages_come_from_the_question_and_the_flagged_hazards():
    passages = passages_for(OESCHINEN_ROUTE, ASSESSED, "What should I know about wind on the ridge?")

    assert 1 <= len(passages) <= 6
    assert len({p.id for p in passages}) == len(passages)


# The asker, over a scripted endpoint


def completion(answer: str | None, reason: str = "ok", passages: list[str] | None = None) -> httpx.Response:
    content = json.dumps({"answer": answer, "reason": reason, "passageIds": passages or []})
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


class Endpoint:
    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        response = self.responses[min(len(self.requests) - 1, len(self.responses) - 1)]
        if isinstance(response, Exception):
            raise response
        return response

    def asker(self, tmp_path, **overrides) -> LlmAsker:
        settings = Settings(
            cache_dir=tmp_path / "cache",
            narration_enabled=True,
            narration_base_url="https://llm.test/v1",
            **overrides,
        )
        return LlmAsker(settings, DiskCache(settings.cache_dir), transport=httpx.MockTransport(self))


async def ask(asker: LlmAsker, question="When is it windiest at Hohtürli?", **fields):
    return await asker.ask(OESCHINEN_ROUTE, ASSESSED, AskRequest(question=question, **fields), DAY, "en")


async def test_an_answer_that_keeps_the_rules_is_served_filled_in_with_what_it_cites(tmp_path):
    passage = passages_for(OESCHINEN_ROUTE, ASSESSED, "When is it windiest at Hohtürli?")[0].id
    endpoint = Endpoint(
        completion("Worst from {h.gusts-hohturli.from}, gusts to {h.gusts-hohturli.gust}.", passages=[passage])
    )

    answer = await ask(endpoint.asker(tmp_path), plan=PLAN)

    assert answer.reason == "ok" and answer.enabled and answer.model
    assert answer.text == "Worst from 11:00, gusts to 60 km/h."
    assert [c.id for c in answer.citations] == [passage]
    sent = endpoint.requests[0]
    assert sent["response_format"]["json_schema"]["name"] == "answer"
    assert "BRIEFING" in sent["messages"][1]["content"]
    assert sent["messages"][-1]["content"] == "QUESTION: When is it windiest at Hohtürli?"


async def test_a_broken_answer_is_sent_back_once_and_the_rewrite_served(tmp_path):
    endpoint = Endpoint(completion("Gusts reach 70 km/h."), completion("Gusts reach {h.gusts-hohturli.gust}."))

    answer = await ask(endpoint.asker(tmp_path))

    assert answer.reason == "ok" and answer.text == "Gusts reach 60 km/h."
    assert len(endpoint.requests) == 2
    assert "70km/h" in endpoint.requests[1]["messages"][-1]["content"]


async def test_an_answer_still_broken_after_the_correction_is_dropped(tmp_path):
    endpoint = Endpoint(completion("It is safe."))

    answer = await ask(endpoint.asker(tmp_path))

    assert answer.reason == "dropped" and answer.text is None
    assert len(endpoint.requests) == 2


async def test_passage_ids_it_was_not_given_are_ignored_not_held_against_it(tmp_path):
    endpoint = Endpoint(completion("Worst from {h.gusts-hohturli.from}.", passages=["gusts-hohturli"]))

    answer = await ask(endpoint.asker(tmp_path))

    assert answer.reason == "ok" and answer.citations == []


async def test_off_topic_is_said_as_such(tmp_path):
    answer = await ask(Endpoint(completion(None, "off_topic")).asker(tmp_path), question="Write me a poem")

    assert answer.reason == "off_topic" and answer.text is None


@pytest.mark.parametrize(
    "response", [httpx.ConnectTimeout("slow"), httpx.Response(401), completion("x").__class__(200, text="nope")]
)
async def test_a_model_that_does_not_answer_is_unavailable_not_an_error(tmp_path, response):
    answer = await ask(Endpoint(response).asker(tmp_path))

    assert answer.reason == "unavailable" and answer.enabled


async def test_without_a_model_nothing_is_called(tmp_path):
    endpoint = Endpoint(completion("x"))
    settings = Settings(cache_dir=tmp_path, narration_enabled=False)
    asker = LlmAsker(settings, DiskCache(tmp_path), transport=httpx.MockTransport(endpoint))

    answer = await ask(asker)

    assert answer.reason == "disabled" and not answer.enabled
    assert endpoint.requests == []


async def test_a_planning_question_is_cached_but_a_live_one_never_is(tmp_path):
    endpoint = Endpoint(completion("Worst from {h.gusts-hohturli.from}."))
    asker = endpoint.asker(tmp_path)

    await ask(asker, plan=PLAN)
    await ask(asker, question="  when is it WINDIEST at Hohtürli? ", plan=PLAN)
    assert len(endpoint.requests) == 1

    await ask(asker, plan=PLAN, live=live())
    await ask(asker, plan=PLAN, live=live())
    assert len(endpoint.requests) == 3


async def test_history_is_sent_before_the_new_question(tmp_path):
    endpoint = Endpoint(completion("Yes, from {h.gusts-hohturli.from}."))
    history = [AskTurn(question="Is it windy?", answer="Gusts reach 60 km/h at Hohtürli.")]

    await ask(endpoint.asker(tmp_path), question="From when?", history=history)

    contents = [m["content"] for m in endpoint.requests[0]["messages"]]
    assert contents[-3] == "QUESTION: Is it windy?"
    assert "Gusts reach 60 km/h" in contents[-2]
    assert contents[-1] == "QUESTION: From when?"


# The endpoint


@pytest.fixture
def client(tmp_path):
    api.ask_limit.seen.clear()
    app = create_app(frontend_dist=tmp_path)
    sources = authored_sources(Settings(cache_dir=tmp_path / "cache"))
    app.dependency_overrides[get_sources] = lambda: sources
    yield TestClient(app)
    api.ask_limit.seen.clear()
    get_settings.cache_clear()


ASK = "/api/routes/oeschinensee-bluemlisalphuette/ask"


def test_the_endpoint_answers_disabled_without_a_model(client):
    response = client.post(ASK, json={"question": "When is it windiest?"})

    assert response.status_code == 200
    assert response.json() == {"enabled": False, "reason": "disabled", "citations": []}


def test_a_question_too_long_or_empty_is_refused(client):
    assert client.post(ASK, json={"question": "x" * 301}).status_code == 422
    assert client.post(ASK, json={"question": ""}).status_code == 422


def test_an_unknown_route_is_404(client):
    assert client.post("/api/routes/nope/ask", json={"question": "Hi"}).status_code == 404


def test_one_client_is_held_to_its_questions_per_minute(client):
    statuses = [client.post(ASK, json={"question": "When?"}).status_code for _ in range(12)]

    assert statuses[:10] == [200] * 10
    assert statuses[10:] == [429, 429]


@pytest.mark.parametrize(("question", "lang"), [("My friend twisted an ankle", "en"), ("Je suis perdu", "fr")])
async def test_an_emergency_the_model_will_not_answer_gets_the_apps_own_sentence(tmp_path, question, lang):
    endpoint = Endpoint(completion(None, "off_topic"))

    answer = await endpoint.asker(tmp_path).ask(
        OESCHINEN_ROUTE, ASSESSED, AskRequest(question=question), DAY, lang
    )

    assert answer.reason == "emergency"
    assert "1414 (Rega)" in answer.text and "Oberbärgli" in answer.text


async def test_a_question_that_is_not_an_emergency_stays_off_topic(tmp_path):
    answer = await ask(Endpoint(completion(None, "off_topic")).asker(tmp_path), question="Write a poem about cats")

    assert answer.reason == "off_topic"
