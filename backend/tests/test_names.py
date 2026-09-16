"""swissnames3d: the places a stop can be named after."""

import pytest
from conftest import FIXTURES, replay, save_fixture

from app.domain import GeoPoint
from app.errors import SourceUnavailable
from app.routing.graph import TrailGraph
from app.sources.http import CachedHttpClient
from app.sources.names import STOP_WORTHY, SwissNamesSource, parse_identify

pytestmark = pytest.mark.anyio

FIXTURE = "swissnames3d_oeschinensee"


def route_coordinates() -> list[tuple[float, float]]:
    graph = TrailGraph.load(FIXTURES / "trails_oeschinensee.sqlite")
    segments = graph.shortest_path([GeoPoint(46.49836, 7.72667), GeoPoint(46.51019, 7.77162)])
    return [(lat, lng) for segment in segments for lat, lng, _ in segment.coordinates]


async def test_record_names_fixture(settings, recording):
    """`pytest --record` refreshes the fixture from the live service. Plain pytest skips."""
    if not recording:
        pytest.skip("offline: run `pytest --record` to refresh the fixture")
    coordinates = route_coordinates()
    async with CachedHttpClient(settings) as client:
        source = SwissNamesSource(settings, client)
        payload = await client.get_json(
            settings.geoadmin_base_url + source.identify_url_path(),
            key=source.cache_key(coordinates),
            ttl_s=0,
            params=source.identify_params(coordinates),
        )
    assert parse_identify(payload), "live response named nothing along the route"
    save_fixture(FIXTURE, payload)


async def test_names_parses_fixture(settings):
    source = SwissNamesSource(settings, CachedHttpClient(settings, transport=replay(FIXTURE)))

    places = await source.along(route_coordinates())

    names = {place.name for place in places}
    # The three places this route is actually planned around — the same ones `mock_data.py`
    # hand-picked, arrived at here from the gazetteer rather than typed in.
    assert "Hohtürli" in names
    assert any("Oberbärgli" in name for name in names)
    assert any("Blüemlisalphütte" in name for name in names)


async def test_the_pass_outranks_the_buildings(settings):
    source = SwissNamesSource(settings, CachedHttpClient(settings, transport=replay(FIXTURE)))

    places = await source.along(route_coordinates())

    pass_place = next(place for place in places if place.name == "Hohtürli")
    assert pass_place.kind == "Pass"
    assert pass_place.weight == max(place.weight for place in places)


async def test_coordinates_come_back_as_latitude_and_longitude(settings):
    """The service answers in LV95; a missing conversion would put the route in the North Sea."""
    source = SwissNamesSource(settings, CachedHttpClient(settings, transport=replay(FIXTURE)))

    places = await source.along(route_coordinates())

    assert all(45.8 < place.point.lat < 47.9 for place in places)
    assert all(5.9 < place.point.lng < 10.6 for place in places)


async def test_a_line_with_nothing_to_identify_is_not_a_request(settings):
    source = SwissNamesSource(settings, CachedHttpClient(settings, transport=replay(FIXTURE)))

    assert await source.along([(46.5, 7.7)]) == []


def test_only_places_worth_stopping_at_are_kept():
    """Ridges, streams and field names are named too, and would make meaningless stops."""
    payload = {
        "results": [
            {"attributes": {"objektart": "Pass", "name": "Hohtürli"}, "geometry": {"x": 2625573, "y": 1148663}},
            {"attributes": {"objektart": "Grat", "name": "Oeschinengrat"}, "geometry": {"x": 2625000, "y": 1148000}},
            {
                "attributes": {"objektart": "Fliessgewaesser", "name": "Öschibach"},
                "geometry": {"x": 2624000, "y": 1149000},
            },
        ]
    }

    places = parse_identify(payload)

    assert [place.name for place in places] == ["Hohtürli"]
    assert "Grat" not in STOP_WORTHY


def test_a_place_without_a_position_is_skipped():
    payload = {"results": [{"attributes": {"objektart": "Pass", "name": "Nowhere"}}]}

    assert parse_identify(payload) == []


def test_parse_rejects_a_shape_it_does_not_recognise():
    with pytest.raises(SourceUnavailable, match="results"):
        parse_identify({"nope": 1})


def test_a_feature_drawn_as_a_line_is_taken_at_a_vertex():
    payload = {
        "results": [
            {
                "attributes": {"objektart": "See", "name": "Oeschinensee"},
                "geometry": {"paths": [[[2622000, 1150000], [2622100, 1150100]]]},
            }
        ]
    }

    places = parse_identify(payload)

    assert len(places) == 1
    assert 46.4 < places[0].point.lat < 46.6
