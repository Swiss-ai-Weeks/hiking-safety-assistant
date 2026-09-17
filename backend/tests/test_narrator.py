"""The live narrator over a replayed chat completions endpoint: what reaches the client, and what does not."""

import json

import httpx
import pytest
from conftest import FIXTURES, load_fixture, save_fixture

from app.config import Settings
from app.mock_data import OESCHINEN_ROUTE, get_assessment
from app.models import AssessmentData, Narration
from app.sources.demo import DemoAssessor
from app.sources.grounded import GroundedAssessor
from app.sources.http import DiskCache
from app.sources.narrator import LlmNarrator

# The demo hazards phrased in both languages. `recorded` says whether `answers` came from a real
# model (`pytest --record` with NARRATION_* set) or were written by hand to stand in for one.
FIXTURE = "narration_oeschinensee"

pytestmark = pytest.mark.anyio


def narration_settings(tmp_path, **overrides) -> Settings:
    return Settings(
        cache_dir=tmp_path / "cache",
        narration_enabled=True,
        narration_base_url="https://llm.test/v1",
        narration_api_key="k",
        **overrides,
    )


def completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


def answer(bodies: dict[str, str]) -> str:
    return json.dumps({"hazards": [{"id": hazard_id, "body": body} for hazard_id, body in bodies.items()]})


class Endpoint:
    """A scripted chat completions endpoint that records what it was sent."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        response = self.responses[min(len(self.requests) - 1, len(self.responses) - 1)]
        if isinstance(response, Exception):
            raise response
        return response

    def narrator(self, settings: Settings) -> LlmNarrator:
        return LlmNarrator(settings, DiskCache(settings.cache_dir), transport=httpx.MockTransport(self))


ASSESSED = get_assessment("assessed")
GOOD = {
    "gusts-hohturli": "Gusts to {gust} km/h at {place} from {from}, where hands are needed for balance.",
    "showers-descent": "Rain from {from} wets the slabs on the way down, walked tired.",
}


async def narrate(narrator: LlmNarrator, lang="en", assessment: AssessmentData = ASSESSED) -> Narration:
    return await narrator.narrate(OESCHINEN_ROUTE, assessment, lang)


async def test_bodies_that_keep_the_rules_are_served_with_their_citations(tmp_path):
    endpoint = Endpoint(completion(answer(GOOD)))
    narration = await narrate(endpoint.narrator(narration_settings(tmp_path)))

    assert narration.enabled and narration.model == "nvidia/nemotron-3-nano-30b-a3b"
    assert {h.id: h.body for h in narration.hazards} == GOOD
    assert narration.hazards[0].citations[0].id == "sac-scale-difficult-mountain-hiking"

    sent = endpoint.requests[0]
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["chat_template_kwargs"] == {"enable_thinking": False}
    assert sent["messages"][0]["content"].startswith("/no_think")


async def test_a_body_that_breaks_a_rule_is_dropped_and_the_rest_kept(tmp_path):
    bad = GOOD | {"showers-descent": "Up to 1.2 mm an hour: fine for a careful hiker."}
    narration = await narrate(Endpoint(completion(answer(bad))).narrator(narration_settings(tmp_path)))

    bodies = {h.id: h.body for h in narration.hazards}
    assert bodies == {"gusts-hohturli": GOOD["gusts-hohturli"], "showers-descent": None}


async def test_a_rejected_body_is_sent_back_once_with_its_reasons(tmp_path):
    bad = GOOD | {"showers-descent": "Rain on the T3 descent from {from}."}
    endpoint = Endpoint(completion(answer(bad)), completion(answer({"showers-descent": GOOD["showers-descent"]})))

    narration = await narrate(endpoint.narrator(narration_settings(tmp_path)))

    assert {h.id: h.body for h in narration.hazards} == GOOD
    assert len(endpoint.requests) == 2
    follow_up = endpoint.requests[1]["messages"]
    assert follow_up[-2]["role"] == "assistant"
    assert "showers-descent" in follow_up[-1]["content"] and "figure" in follow_up[-1]["content"]
    assert "gusts-hohturli" not in follow_up[-1]["content"]


async def test_a_body_still_broken_after_the_correction_is_dropped(tmp_path):
    bad = GOOD | {"showers-descent": "Rain on the T3 descent."}
    endpoint = Endpoint(completion(answer(bad)))

    narration = await narrate(endpoint.narrator(narration_settings(tmp_path)))

    assert {h.id: h.body for h in narration.hazards}["showers-descent"] is None
    assert len(endpoint.requests) == 2


async def test_reasoning_and_fences_around_the_answer_are_tolerated(tmp_path):
    content = f"<think>exposed col, wet descent</think>\n```json\n{answer(GOOD)}\n```"
    narration = await narrate(Endpoint(completion(content)).narrator(narration_settings(tmp_path)))

    assert all(h.body for h in narration.hazards)


@pytest.mark.parametrize(
    "response",
    [
        completion("I cannot help with that."),
        httpx.Response(200, json={"unexpected": True}),
        httpx.Response(401, json={"error": "bad key"}),
        httpx.ConnectTimeout("slow"),
    ],
)
async def test_a_failing_model_costs_the_phrasing_not_the_citations(tmp_path, response):
    narration = await narrate(Endpoint(response).narrator(narration_settings(tmp_path)))

    assert narration.enabled
    assert [h.body for h in narration.hazards] == [None, None]
    assert all(h.citations for h in narration.hazards)


async def test_a_server_that_rejects_structured_output_is_asked_plainly(tmp_path):
    endpoint = Endpoint(httpx.Response(400, json={"error": "response_format"}), completion(answer(GOOD)))
    narration = await narrate(endpoint.narrator(narration_settings(tmp_path)))

    assert all(h.body for h in narration.hazards)
    assert "response_format" not in endpoint.requests[1]
    assert "chat_template_kwargs" not in endpoint.requests[1]


async def test_a_transient_failure_is_retried_once(tmp_path):
    endpoint = Endpoint(httpx.Response(503), completion(answer(GOOD)))
    narration = await narrate(endpoint.narrator(narration_settings(tmp_path)))

    assert all(h.body for h in narration.hazards)
    assert len(endpoint.requests) == 2


async def test_the_same_assessment_is_phrased_once_per_language(tmp_path):
    endpoint = Endpoint(completion(answer(GOOD)))
    narrator = endpoint.narrator(narration_settings(tmp_path))

    await narrate(narrator)
    await narrate(narrator)
    assert len(endpoint.requests) == 1
    await narrate(narrator, lang="fr")
    assert len(endpoint.requests) == 2


async def test_without_an_endpoint_nothing_is_called_and_citations_still_come(tmp_path):
    endpoint = Endpoint(completion(answer(GOOD)))
    narration = await narrate(endpoint.narrator(Settings(cache_dir=tmp_path, narration_enabled=True)))

    assert not narration.enabled and narration.model is None
    assert [h.body for h in narration.hazards] == [None, None]
    assert all(h.citations for h in narration.hazards)
    assert endpoint.requests == []


async def test_an_assessment_without_hazards_asks_nothing(tmp_path):
    endpoint = Endpoint(completion(answer(GOOD)))
    narrator = endpoint.narrator(narration_settings(tmp_path))
    narration = await narrate(narrator, assessment=get_assessment("not_assessable"))

    assert narration.hazards == [] and endpoint.requests == []


@pytest.mark.parametrize("lang", ["en", "fr"])
async def test_the_fixture_answers_serve_what_the_fixture_says(tmp_path, recording, lang):
    """The answers in the fixture, through parsing and the guard, give exactly its `served` narration.

    `frontend/src/i18n/copy-rules.test.ts` holds the served bodies to the client's copy rules, so this
    is also what keeps that test looking at what the backend would really serve.
    """
    assessment = await GroundedAssessor(DemoAssessor()).assess(OESCHINEN_ROUTE, "assessed")
    if recording:
        settings = Settings(cache_dir=tmp_path / "cache")
        if not settings.narration_configured:
            pytest.skip("recording narration needs NARRATION_ENABLED, NARRATION_BASE_URL and a key")
        fixture = load_fixture(FIXTURE) if (FIXTURES / f"{FIXTURE}.json").is_file() else {}

        captured: dict[str, list[str]] = {lang: []}

        class Capturing(LlmNarrator):
            async def _complete(self, messages):
                content = await super()._complete(messages)
                captured[lang].append(content)
                return content

        served = await Capturing(settings, DiskCache(settings.cache_dir)).narrate(OESCHINEN_ROUTE, assessment, lang)
        fixture.update(recorded=True, model=settings.narration_model)
        hazards = [h.model_dump(mode="json", by_alias=True, exclude_none=True) for h in assessment.hazards]
        fixture.setdefault("hazards", hazards)
        fixture.setdefault("answers", {})[lang] = captured[lang]
        fixture.setdefault("served", {})[lang] = served.model_dump(mode="json", by_alias=True, exclude_none=True)
        save_fixture(FIXTURE, fixture)

    fixture = load_fixture(FIXTURE)
    # The first answer, then the correction turn if the guard sent one back.
    answers = fixture["answers"][lang]
    endpoint = Endpoint(*(completion(content) for content in ([answers] if isinstance(answers, str) else answers)))
    served = await endpoint.narrator(narration_settings(tmp_path, narration_model=fixture["model"])).narrate(
        OESCHINEN_ROUTE, assessment, lang
    )

    assert served.model_dump(mode="json", by_alias=True, exclude_none=True) == fixture["served"][lang]
