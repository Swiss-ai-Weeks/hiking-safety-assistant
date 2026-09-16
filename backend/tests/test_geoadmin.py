"""The one live source Phase 0 implements, checked against a recorded real response."""

import pytest
from conftest import load_fixture, replay, save_fixture

from app.domain import GeoPoint
from app.sources.base import SourceUnavailable
from app.sources.geoadmin import SEARCH_PATH, GeoAdminRouteSource, clean_label, parse_search
from app.sources.http import CachedHttpClient, CacheKey

pytestmark = pytest.mark.anyio

FIXTURE = "geoadmin_search_oeschinensee"
QUERY = "Oeschinensee"


async def test_record_search_fixture(settings, recording):
    """`pytest --record` refreshes the fixture from the live service. Plain pytest skips."""
    if not recording:
        pytest.skip("offline: run `pytest --record` to refresh the fixture")
    async with CachedHttpClient(settings) as client:
        payload = await client.get_json(
            settings.geoadmin_base_url + SEARCH_PATH,
            key=CacheKey(source="geoadmin", endpoint="search", params={"q": QUERY}),
            ttl_s=0,
            params={"searchText": QUERY, "type": "locations", "sr": "4326", "limit": "10"},
        )
    assert parse_search(payload), "live response contained no place results"
    save_fixture(FIXTURE, payload)


async def test_search_parses_fixture(settings):
    source = GeoAdminRouteSource(settings, CachedHttpClient(settings, transport=replay(FIXTURE)))

    hits = await source.search(QUERY)

    assert hits, "the recorded response should yield at least the lake itself"
    lake = hits[0]
    assert "Oeschinensee" in lake.name
    # Kandersteg, roughly: the recorded coordinates are real ones.
    assert 46.4 < lake.point.lat < 46.6
    assert 7.6 < lake.point.lng < 7.8
    # Search carries no altitude; the elevation source fills it in.
    assert lake.point.elevation_m is None


async def test_search_drops_markup_and_postal_addresses(settings):
    source = GeoAdminRouteSource(settings, CachedHttpClient(settings, transport=replay(FIXTURE)))

    hits = await source.search(QUERY)

    assert all("<" not in hit.name for hit in hits), "labels arrive as HTML and must be cleaned"
    # "Oeschinensee 2b 3718 Kandersteg" is a building address, not somewhere you hike to.
    assert not any("3718" in hit.name for hit in hits)


async def test_search_is_cached(settings):
    transport = replay(FIXTURE)
    source = GeoAdminRouteSource(settings, CachedHttpClient(settings, transport=transport))

    first = await source.search(QUERY)
    second = await source.search(QUERY.upper())

    # The key is the folded query, so a differently-cased search reuses the entry.
    assert [hit.name for hit in first] == [hit.name for hit in second]
    assert len(list(settings.cache_dir.glob("geoadmin/*.json"))) == 1


def test_clean_label_strips_the_match_markup():
    assert clean_label("<i>See</i> <b>Oeschinensee</b> (BE) - Kandersteg") == "See Oeschinensee (BE) - Kandersteg"


def test_parse_search_rejects_an_unknown_shape():
    with pytest.raises(SourceUnavailable, match="results"):
        parse_search({"unexpected": True})


def test_parse_search_skips_incomplete_results():
    payload = load_fixture(FIXTURE)
    payload["results"].append({"attrs": {"origin": "gazetteer", "label": "No coordinates"}})

    assert all(isinstance(hit.point, GeoPoint) for hit in parse_search(payload))
