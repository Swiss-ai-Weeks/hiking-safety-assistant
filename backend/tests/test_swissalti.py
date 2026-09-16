"""swissALTI3D, against a recorded profile of the real demo route."""

import pytest
from conftest import FIXTURES, replay, save_fixture

from app.domain import GeoPoint
from app.errors import SourceUnavailable
from app.routing.graph import TrailGraph
from app.routing.stops import flatten
from app.sources.http import CachedHttpClient, CacheKey
from app.sources.swissalti import (
    PROFILE_PATH,
    SwissAltiElevationSource,
    parse_profile,
    profile_request,
)

pytestmark = pytest.mark.anyio

FIXTURE = "swissalti_profile_oeschinensee"


def route_points() -> list[GeoPoint]:
    """The same line the fixture was recorded over, so heights and points stay in step."""
    graph = TrailGraph.load(FIXTURES / "trails_oeschinensee.sqlite")
    segments = graph.shortest_path([GeoPoint(46.49836, 7.72667), GeoPoint(46.51019, 7.77162)])
    return [GeoPoint(v.point.lat, v.point.lng) for v in flatten(segments)]


async def test_record_profile_fixture(settings, recording):
    """`pytest --record` refreshes the fixture from the live service. Plain pytest skips.

    What is saved is the raw response body, not anything this code derived from it — a fixture
    that had been through our own parser could not catch our own parser being wrong.
    """
    if not recording:
        pytest.skip("offline: run `pytest --record` to refresh the fixture")
    points = route_points()
    async with CachedHttpClient(settings) as client:
        payload = await client.post_json(
            settings.geoadmin_base_url + PROFILE_PATH,
            key=CacheKey(source="swissalti3d", endpoint="record", params={"n": len(points)}),
            ttl_s=0,
            data=profile_request(points),
        )
    assert parse_profile(payload, points).ascent_m > 0, "live response carried no climb"
    save_fixture(FIXTURE, payload)


async def test_profile_parses_fixture(settings):
    points = route_points()
    source = SwissAltiElevationSource(settings, CachedHttpClient(settings, transport=replay(FIXTURE)))

    profile = await source.profile(points)

    assert len(profile.points) == len(points), "one height per point the caller asked about"
    assert all(point.elevation_m is not None for point in profile.points)
    # Oeschinensee to Blüemlisalphütte: from about 1 720 m to about 2 835 m.
    assert 1600 < profile.points[0].elevation_m < 1800
    assert 2700 < profile.points[-1].elevation_m < 2900


async def test_the_profile_measures_the_climb(settings):
    source = SwissAltiElevationSource(settings, CachedHttpClient(settings, transport=replay(FIXTURE)))

    profile = await source.profile(route_points())

    # `mock_data.py` hand-authored 1 220 m for the whole out-and-back; this is the one-way climb.
    assert 1000 < profile.ascent_m < 1400
    assert profile.descent_m < profile.ascent_m


async def test_a_profile_needs_a_line(settings):
    source = SwissAltiElevationSource(settings, CachedHttpClient(settings, transport=replay(FIXTURE)))

    with pytest.raises(SourceUnavailable, match="at least two points"):
        await source.profile([GeoPoint(46.5, 7.7)])


def test_parse_rejects_a_shape_it_does_not_recognise():
    with pytest.raises(SourceUnavailable, match="non-empty list"):
        parse_profile({"error": "nope"}, [GeoPoint(46.5, 7.7), GeoPoint(46.6, 7.8)])

    with pytest.raises(SourceUnavailable, match="no elevations"):
        parse_profile([{"dist": 0}], [GeoPoint(46.5, 7.7), GeoPoint(46.6, 7.8)])


def test_a_coarser_model_is_used_where_the_finest_one_is_missing():
    """Outside DTM2 coverage only the coarser models answer. Any height beats none."""
    points = [GeoPoint(46.5, 7.7), GeoPoint(46.6, 7.8)]

    profile = parse_profile([{"alts": {"COMB": None, "DTM25": 1500.0}}, {"alts": {"DTM25": 1600.0}}], points)

    assert [point.elevation_m for point in profile.points] == [1500.0, 1600.0]
