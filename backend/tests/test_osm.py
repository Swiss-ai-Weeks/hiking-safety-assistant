"""OSM grades, and the rules that decide when they may override swisstopo's official class."""

import pytest
from conftest import FIXTURES, load_fixture, replay, save_fixture
from shapely.geometry import LineString

from app.domain import GeoPoint
from app.errors import SourceUnavailable
from app.projection import TO_LV95
from app.routing.grades import GradedWay, GradeIndex, bearing_of
from app.routing.graph import TrailGraph
from app.sources.http import CachedHttpClient
from app.sources.osm import OverpassGradeSource, parse_ways

pytestmark = pytest.mark.anyio

FIXTURE = "overpass_sac_oeschinensee"
# The demo route's box, widened as `TlmRouteSource` widens it.
BBOX = (46.488, 7.716, 46.521, 7.782)


def route_segments():
    graph = TrailGraph.load(FIXTURES / "trails_oeschinensee.sqlite")
    return graph.shortest_path([GeoPoint(46.49836, 7.72667), GeoPoint(46.51019, 7.77162)])


def way(grade, cables, points):
    """A graded way from WGS84 (lat, lng) points, projected as the real ones are."""
    eastings, northings = TO_LV95.transform([lng for _, lng in points], [lat for lat, _ in points])
    line = LineString(list(zip(eastings, northings, strict=True)))
    return GradedWay(grade, cables, line, bearing_of(line))


async def test_record_overpass_fixture(settings, recording):
    """`pytest --record` refreshes the fixture from Overpass. Plain pytest skips."""
    if not recording:
        pytest.skip("offline: run `pytest --record` to refresh the fixture")
    async with CachedHttpClient(settings) as client:
        source = OverpassGradeSource(settings, client)
        # Reach past the cache so a recording is always a fresh call.
        payload = await client.get_json(
            settings.overpass_url,
            key=source.cache_key(BBOX),
            ttl_s=0,
            params={"data": source.query(BBOX)},
        )
    assert parse_ways(payload), "live response carried no graded ways"
    save_fixture(FIXTURE, payload)


async def test_overpass_parses_fixture(settings):
    source = OverpassGradeSource(settings, CachedHttpClient(settings, transport=replay(FIXTURE)))

    index = await source.grades_for(BBOX)

    assert index.ways, "the Bernese Oberland is well tagged; this should not come back empty"
    grades = {way.grade for way in index.ways}
    # The area really does carry the harder grades, which is why OSM is worth consulting at all.
    assert {"T3", "T4"} <= grades


def test_parse_keeps_only_ways_that_say_something():
    line = [{"lat": 46.5, "lon": 7.7}, {"lat": 46.6, "lon": 7.8}]
    payload = {
        "elements": [
            {"tags": {"sac_scale": "alpine_hiking"}, "geometry": line},
            {"tags": {"safety_rope": "yes"}, "geometry": line},
            # Nothing to contribute: an untagged path only slows the spatial index down.
            {"tags": {"highway": "path"}, "geometry": line},
            # Too short to have a direction.
            {"tags": {"sac_scale": "hiking"}, "geometry": line[:1]},
        ]
    }

    ways = parse_ways(payload)

    assert [(w.grade, w.cables) for w in ways] == [("T4", False), (None, True)]


def test_parse_rejects_a_shape_it_does_not_recognise():
    with pytest.raises(SourceUnavailable, match="elements"):
        parse_ways({"nope": []})


def test_ladders_and_via_ferrata_also_mean_cables():
    """`assisted_trail`, which the plan named, has no coverage here; these are the real tags."""
    geometry = [{"lat": 46.5, "lon": 7.7}, {"lat": 46.6, "lon": 7.8}]
    payload = {
        "elements": [
            {"tags": {"ladder": "yes"}, "geometry": geometry},
            {"tags": {"via_ferrata_scale": "B"}, "geometry": geometry},
        ]
    }

    assert all(way.cables for way in parse_ways(payload))


def test_an_empty_index_leaves_the_official_class_alone():
    segments = route_segments()

    grade, cables, estimated = GradeIndex([]).refine(segments[0].coordinates, "T2")

    assert (grade, cables) == ("T2", False)
    assert estimated, "with nothing to corroborate it, the class is an estimate and says so"


def test_osm_can_raise_the_official_class_but_never_lower_it():
    segments = route_segments()
    line = [(lat, lng) for lat, lng, _ in segments[7].coordinates]

    harder_index = GradeIndex([way("T4", False, line)])
    easier_index = GradeIndex([way("T1", False, line)])

    assert harder_index.refine(segments[7].coordinates, "T2")[0] == "T4"
    # swisstopo signposts the route; a crowd-sourced under-grade does not get to overrule that.
    assert easier_index.refine(segments[7].coordinates, "T2")[0] == "T2"


def test_a_single_stray_match_cannot_regrade_a_whole_segment():
    """The rule that stopped a 13 m connector reading T5 off one nearby via ferrata."""
    segments = route_segments()
    long_segment = max(segments, key=lambda s: s.length_m)
    line = [(lat, lng) for lat, lng, _ in long_segment.coordinates]

    # One short T5 way over the first fraction of a 2 km segment: real, but not the segment.
    stray = GradeIndex([way("T5", True, line[:2])])

    grade, _cables, _estimated = stray.refine(long_segment.coordinates, "T2")
    assert grade == "T2"


def test_a_hard_stretch_that_covers_enough_ground_does_regrade():
    segments = route_segments()
    long_segment = max(segments, key=lambda s: s.length_m)
    line = [(lat, lng) for lat, lng, _ in long_segment.coordinates]

    # The upper half of the same segment: corroborated across a real distance.
    sustained = GradeIndex([way("T4", True, line[len(line) // 2 :])])

    grade, cables, estimated = sustained.refine(long_segment.coordinates, "T2")
    assert grade == "T4"
    assert cables
    assert not estimated


def test_cables_are_assumed_from_t4_upwards():
    """Erring towards warning a hiker about equipment they turn out not to need."""
    segments = route_segments()

    _grade, cables, _estimated = GradeIndex([]).refine(segments[0].coordinates, "T4")

    assert cables


async def test_grades_are_cached_per_box(settings):
    transport = replay(FIXTURE)
    source = OverpassGradeSource(settings, CachedHttpClient(settings, transport=transport))

    await source.grades_for(BBOX)
    # Rounded to two decimals, so a route a few metres over reuses the same answer.
    await source.grades_for((BBOX[0] + 0.0001, BBOX[1], BBOX[2], BBOX[3]))

    assert len(list(settings.cache_dir.glob("overpass/*.json"))) == 1


def test_the_fixture_is_real_overpass_output():
    payload = load_fixture(FIXTURE)

    assert isinstance(payload["elements"], list)
    assert any("sac_scale" in (element.get("tags") or {}) for element in payload["elements"])
