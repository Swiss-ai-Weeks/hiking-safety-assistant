"""The HTTP layer: retry on what is worth retrying, cache on what identifies a forecast."""

import httpx
import pytest
from conftest import responses

from app.domain import GeoPoint
from app.sources.base import SourceUnavailable
from app.sources.http import CachedHttpClient, CacheKey

pytestmark = pytest.mark.anyio

URL = "https://example.test/forecast"
HOHTURLI = GeoPoint(46.4888, 7.7717, 2778)


def key(**overrides) -> CacheKey:
    fields = {
        "source": "icon",
        "endpoint": "forecast",
        "point": HOHTURLI,
        "model_run": "ICON-CH1 2026-09-16T06:00Z",
        "hour": 11 * 60,
    }
    return CacheKey(**(fields | overrides))


async def test_the_same_point_hour_and_run_is_fetched_once(settings):
    transport, seen = responses(httpx.Response(200, json={"gust": 55}))

    async with CachedHttpClient(settings, transport=transport) as client:
        first = await client.get_json(URL, key=key(), ttl_s=600)
        second = await client.get_json(URL, key=key(), ttl_s=600)

    assert first == second == {"gust": 55}
    assert len(seen) == 1


async def test_an_expired_entry_is_refetched(settings):
    transport, seen = responses(httpx.Response(200, json={"gust": 55}), httpx.Response(200, json={"gust": 70}))

    async with CachedHttpClient(settings, transport=transport) as client:
        first = await client.get_json(URL, key=key(), ttl_s=600)
        # A TTL of zero makes the entry stale the moment it is written.
        second = await client.get_json(URL, key=key(), ttl_s=0)

    assert (first, second) == ({"gust": 55}, {"gust": 70})
    assert len(seen) == 2


@pytest.mark.parametrize(
    "different",
    [
        {"point": GeoPoint(46.4915, 7.751, 1978)},
        {"hour": 14 * 60},
        {"model_run": "ICON-CH1 2026-09-16T09:00Z"},
        {"endpoint": "gusts"},
    ],
    ids=["point", "hour", "run", "endpoint"],
)
def test_the_key_separates_what_identifies_a_value(different):
    assert key().digest() != key(**different).digest()


def test_the_key_ignores_coordinate_noise():
    # Interpolated route points wobble far below the ~11 m the key rounds to.
    nudged = GeoPoint(HOHTURLI.lat + 1e-9, HOHTURLI.lng - 1e-9, HOHTURLI.elevation_m)

    assert key().digest() == key(point=nudged).digest()


async def test_a_5xx_is_retried_then_succeeds(settings):
    transport, seen = responses(httpx.Response(503), httpx.Response(200, json={"gust": 55}))

    async with CachedHttpClient(settings, transport=transport) as client:
        assert await client.get_json(URL, key=key(), ttl_s=600) == {"gust": 55}

    assert len(seen) == 2


async def test_it_gives_up_after_the_configured_attempts(settings):
    transport, seen = responses(httpx.Response(502))

    async with CachedHttpClient(settings, transport=transport) as client:
        with pytest.raises(SourceUnavailable, match="after 3 attempts"):
            await client.get_json(URL, key=key(), ttl_s=600)

    assert len(seen) == settings.http_attempts


async def test_a_4xx_is_not_retried(settings):
    transport, seen = responses(httpx.Response(404))

    async with CachedHttpClient(settings, transport=transport) as client:
        with pytest.raises(SourceUnavailable, match="404"):
            await client.get_json(URL, key=key(), ttl_s=600)

    # The request itself is wrong; repeating it would only be rude.
    assert len(seen) == 1


async def test_a_transport_error_is_retried(settings):
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) < 3:
            raise httpx.ConnectError("no route to host", request=request)
        return httpx.Response(200, json={"gust": 55})

    async with CachedHttpClient(settings, transport=httpx.MockTransport(handler)) as client:
        assert await client.get_json(URL, key=key(), ttl_s=600) == {"gust": 55}

    assert len(attempts) == 3


async def test_a_non_json_body_is_a_source_failure(settings):
    transport, _ = responses(httpx.Response(200, text="<html>maintenance</html>"))

    async with CachedHttpClient(settings, transport=transport) as client:
        with pytest.raises(SourceUnavailable, match="non-JSON"):
            await client.get_json(URL, key=key(), ttl_s=600)


async def test_a_corrupt_entry_is_a_miss_not_a_crash(settings):
    transport, seen = responses(httpx.Response(200, json={"gust": 55}))

    async with CachedHttpClient(settings, transport=transport) as client:
        await client.get_json(URL, key=key(), ttl_s=600)
        client.cache.path_for(key()).write_text("{half-written", encoding="utf-8")

        assert await client.get_json(URL, key=key(), ttl_s=600) == {"gust": 55}

    assert len(seen) == 2


async def test_a_cache_entry_records_what_it_is(settings):
    transport, _ = responses(httpx.Response(200, json={"gust": 55}))

    async with CachedHttpClient(settings, transport=transport) as client:
        await client.get_json(URL, key=key(), ttl_s=600)
        entry = client.cache.path_for(key()).read_text(encoding="utf-8")

    # A cache directory should be readable by a human debugging a stale forecast on the VM.
    assert '"hour": 660' in entry
    assert '"modelRun": "ICON-CH1 2026-09-16T06:00Z"' in entry
