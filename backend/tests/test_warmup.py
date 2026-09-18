"""The startup warm-up: every route, day and language once, and a failure costs only its own step."""

from dataclasses import replace

import pytest
from authored import authored_sources

from app import warmup
from app.config import Settings

pytestmark = pytest.mark.anyio

ROUTE_ID = "oeschinensee-bluemlisalphuette"


class Counting:
    def __init__(self, inner, fail_on=None):
        self.inner = inner
        self.calls: list[tuple] = []
        self.fail_on = fail_on

    async def assess(self, route, day=None):
        self.calls.append((route.id, day))
        if self.fail_on == day:
            raise RuntimeError("bug")
        return await self.inner.assess(route, day)

    async def narrate(self, route, assessment, lang):
        self.calls.append((route.id, lang))
        return await self.inner.narrate(route, assessment, lang)

    async def recheck(self, day=None):
        return True


@pytest.fixture
def sources(tmp_path):
    return authored_sources(Settings(cache_dir=tmp_path / "cache"))


async def test_warm_assesses_today_and_tomorrow_and_narrates_both_languages(sources):
    assessor, narrator = Counting(sources.assessor), Counting(sources.narrator)

    done = await warmup.warm(replace(sources, assessor=assessor, narrator=narrator), [ROUTE_ID])

    assert len(assessor.calls) == 2
    assert sorted(lang for _, lang in narrator.calls) == ["en", "en", "fr", "fr"]
    assert len(done) == 6


async def test_a_failing_day_does_not_stop_the_next(sources):
    probe = Counting(sources.assessor)
    await warmup.warm(replace(sources, assessor=probe), [ROUTE_ID], langs=())
    today = probe.calls[0][1]
    assessor = Counting(sources.assessor, fail_on=today)

    done = await warmup.warm(replace(sources, assessor=assessor), ["unknown-route", ROUTE_ID], langs=())

    assert len(assessor.calls) == 2
    assert len(done) == 1


def test_only_one_worker_claims_the_warm_up(tmp_path):
    first = warmup.claim(tmp_path)
    try:
        assert first is not None
        assert warmup.claim(tmp_path) is None
    finally:
        first.close()


async def test_nothing_warms_when_disabled_or_with_no_routes(sources, tmp_path):
    assert warmup.start(Settings(cache_dir=tmp_path, warmup_routes=[ROUTE_ID]), sources) is None
    assert warmup.start(Settings(cache_dir=tmp_path, warmup_enabled=True), sources) is None
