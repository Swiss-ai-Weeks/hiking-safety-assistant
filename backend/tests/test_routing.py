"""Graph, stop selection and assembly, entirely offline.

`tests/fixtures/trails_oeschinensee.sqlite` is the real swissTLM3D import clipped to a box around
the demo route — 90 edges out of the national 409,276, built by
`python -m scripts.import_trails --bbox 2620500,1148500,2627000,1152500`. It is real swisstopo
geometry, so these are not tests against invented data, and at 256 KB it is small enough to commit.
"""

import pytest
from conftest import FIXTURES

from app.domain import GeoPoint, NamedPlace
from app.errors import SourceUnavailable
from app.models import RouteRequest
from app.routing.build import build_route, route_id_for
from app.routing.graph import TrailGraph
from app.routing.stops import MAX_STOPS, crux_index, flatten, with_elevations

pytestmark = pytest.mark.anyio

TRAILS = FIXTURES / "trails_oeschinensee.sqlite"

# Real coordinates from the swisstopo gazetteer, not the illustrative ones in `mock_data.py`.
OESCHINENSEE = GeoPoint(46.49836, 7.72667)
BLUEMLISALPHUETTE = GeoPoint(46.51019, 7.77162)
HOHTUERLI = GeoPoint(46.51112, 7.77020)

PLACES = [
    NamedPlace("Hohtürli", HOHTUERLI, "Pass", 10),
    NamedPlace("Berghaus Oberbärgli", GeoPoint(46.50883, 7.73700), "Gebaeude", 7),
    NamedPlace("Blüemlisalphütte SAC", BLUEMLISALPHUETTE, "Gebaeude", 7),
]


@pytest.fixture(scope="module")
def graph() -> TrailGraph:
    return TrailGraph.load(TRAILS)


@pytest.fixture(scope="module")
def segments(graph):
    return graph.shortest_path([OESCHINENSEE, BLUEMLISALPHUETTE])


def request_for(**overrides) -> RouteRequest:
    body = {
        "from": {"name": "Oeschinensee", "latLng": [OESCHINENSEE.lat, OESCHINENSEE.lng]},
        "to": {"name": "Blüemlisalphütte", "latLng": [BLUEMLISALPHUETTE.lat, BLUEMLISALPHUETTE.lng]},
    }
    return RouteRequest.model_validate({**body, **overrides})


def test_a_missing_graph_says_how_to_build_one(tmp_path):
    with pytest.raises(SourceUnavailable, match="import_trails"):
        TrailGraph.load(tmp_path / "nothing.sqlite")


def test_every_segment_is_traversable_in_both_directions(graph):
    for tail, head in list(graph.graph.edges())[:50]:
        assert graph.graph.has_edge(head, tail), "walking back down the same path must be possible"


def test_reversing_a_segment_exchanges_ascent_and_descent(graph):
    tail, head = next(iter(graph.graph.edges()))
    up, down = graph.graph[tail][head]["segment"], graph.graph[head][tail]["segment"]

    assert up.ascent_m == down.descent_m
    assert up.descent_m == down.ascent_m
    assert up.coordinates == down.coordinates[::-1]


def test_snapping_reaches_the_pass_itself(graph):
    """Nodes sit at the ends of TLM3D lines, which are far apart; snapping is to the line."""
    node = graph.nearest_node(HOHTUERLI)
    heights = [segment["segment"].coordinates[0][2] for segment in graph.graph[node].values()]

    # Hohtürli is at 2 778 m, and `mock_data.py` says so too — arrived at independently here.
    assert any(abs(height - 2778) < 30 for height in heights)


def test_a_point_off_the_network_is_refused_rather_than_snapped(graph):
    # Bern, well outside the clipped region.
    with pytest.raises(SourceUnavailable, match="no marked trail"):
        graph.nearest_node(GeoPoint(46.9480, 7.4474))


def test_the_routed_line_climbs_from_the_lake_to_the_hut(segments):
    vertices = flatten(segments)

    assert len(segments) > 1
    assert vertices[0].point.elevation_m < 1800
    assert vertices[-1].point.elevation_m > 2800
    # About 5 km and 1 200 m one way; `mock_data.py` hand-authored 11.2 km and 1 220 m out and back.
    assert 4.5 < vertices[-1].distance_m / 1000 < 5.5
    assert 1000 < sum(s.ascent_m for s in segments) < 1300


def test_routing_needs_two_points(graph):
    with pytest.raises(SourceUnavailable, match="at least a start"):
        graph.shortest_path([OESCHINENSEE])


def test_flatten_does_not_repeat_the_joins_between_segments(segments):
    vertices = flatten(segments)

    raw = sum(len(segment.coordinates) for segment in segments)
    assert len(vertices) < raw, "the shared vertex at each join should be kept once"
    # Distance walked only ever increases.
    assert all(b.distance_m >= a.distance_m for a, b in zip(vertices, vertices[1:], strict=False))


def test_elevations_are_only_swapped_in_when_they_line_up(segments):
    vertices = flatten(segments)

    assert with_elevations(vertices, None) is vertices
    with pytest.raises(ValueError, match="heights for"):
        with_elevations(vertices, [1000.0] * (len(vertices) - 1))

    swapped = with_elevations(vertices, [1234.0] * len(vertices))
    assert all(vertex.point.elevation_m == 1234.0 for vertex in swapped)


def test_the_crux_is_a_sustained_climb_not_the_steepest_connector(segments):
    vertices = flatten(segments)

    crux = vertices[crux_index(vertices, segments)]

    # High on the route, near the pass rather than on some 24 m step low down.
    assert crux.point.elevation_m > 2500
    assert crux.distance_m > vertices[-1].distance_m / 2


def test_build_produces_a_timeline_the_frontend_can_walk(segments):
    route = build_route(request_for(), segments, flatten(segments), PLACES)

    assert 4 <= len(route.stops) <= MAX_STOPS
    # `computeArrivals` accumulates `legMinutes` in order, so the first stop must cost nothing.
    assert route.stops[0].leg_minutes == 0
    assert all(stop.leg_minutes >= 0 for stop in route.stops)
    # Out and back: an odd number of stops, mirrored around the single break.
    assert len(route.stops) % 2 == 1
    assert [stop.break_minutes is not None for stop in route.stops].count(True) == 1

    ids = [stop.id for stop in route.stops]
    assert len(set(ids)) == len(ids), "stop ids are object keys elsewhere and must be unique"
    waypoints = {waypoint.id for waypoint in route.waypoints}
    assert all(stop.waypoint_id in waypoints for stop in route.stops)


def test_build_names_the_stops_after_real_places(segments):
    route = build_route(request_for(), segments, flatten(segments), PLACES)

    names = [waypoint.name for waypoint in route.waypoints]
    assert "Hohtürli" in names
    assert "Berghaus Oberbärgli" in names
    # Ids are ASCII even where the names are not: they travel in URLs and as object keys.
    assert all(stop.id.isascii() for stop in route.stops)


def test_the_crux_and_bail_out_are_derived_from_the_route(segments):
    route = build_route(request_for(), segments, flatten(segments), PLACES)

    assert route.crux_stop_id in {stop.id for stop in route.stops}
    assert route.bailout_stop_id in {stop.id for stop in route.stops}
    # The crux of this route is the pass, and the bail-out is the hut below it.
    assert route.crux_stop_id.startswith("hohturli")
    assert route.bailout_name == "Berghaus Oberbärgli"


def test_legs_index_into_the_geometry_the_map_draws(segments):
    route = build_route(request_for(), segments, flatten(segments), PLACES)

    assert len(route.geometry) == len(route.elevations)
    for leg in route.legs:
        assert 0 <= leg.from_index < leg.to_index < len(route.geometry)
        assert leg.distance_km > 0
    # Consecutive legs join end to end, so the drawn line has no gaps.
    assert all(a.to_index == b.from_index for a, b in zip(route.legs, route.legs[1:], strict=False))
    assert route.legs[0].from_index == 0
    assert route.legs[-1].to_index == len(route.geometry) - 1


def test_every_leg_lists_the_return_stops_that_recross_it(segments):
    route = build_route(request_for(), segments, flatten(segments), PLACES)
    ids = {stop.id for stop in route.stops}

    for leg in route.legs:
        assert leg.from_stop in ids and leg.to_stop in ids
        assert set(leg.stop_ids) <= ids
        assert leg.from_stop in leg.stop_ids and leg.to_stop in leg.stop_ids


def test_the_route_is_graded_by_its_hardest_leg(segments):
    route = build_route(request_for(), segments, flatten(segments), PLACES)

    assert route.grade == max((leg.grade for leg in route.legs), key=lambda g: int(g[1]))


def test_a_route_with_no_named_places_still_builds(segments):
    """swissnames3d failing costs labels, not the route."""
    route = build_route(request_for(), segments, flatten(segments), [])

    assert len(route.stops) >= 3
    assert route.stops[0].label.place == "Oeschinensee"


def test_the_same_search_always_gets_the_same_id():
    assert route_id_for(request_for()) == route_id_for(request_for())
    assert route_id_for(request_for()) != route_id_for(
        request_for(to={"name": "Hohtürli", "latLng": [HOHTUERLI.lat, HOHTUERLI.lng]})
    )
    # `r` plus a 16-character digest: the shape `store/plan.ts` recognises as expiring.
    assert route_id_for(request_for()).startswith("r")
    assert len(route_id_for(request_for())) == 17
