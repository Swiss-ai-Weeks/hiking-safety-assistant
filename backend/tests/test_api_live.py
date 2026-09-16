"""The routing endpoints end to end, with every live source replayed from a recorded response.

This is the first use of `app.dependency_overrides[get_sources]`, which is the seam Phase 0 left
for exactly this: the whole request path runs — routing, timing, stop selection, serialisation —
against real recorded data and no network.
"""

import pytest
from conftest import FIXTURES, replay, replay_by_url
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.sources import get_sources
from app.sources.base import Sources
from app.sources.http import CachedHttpClient
from app.sources.live import NotImplementedAssessor, NotImplementedWarningSource, NotImplementedWeatherSource
from app.sources.names import SwissNamesSource
from app.sources.osm import OverpassGradeSource
from app.sources.swissalti import SwissAltiElevationSource
from app.sources.tlm import TlmRouteSource

BODY = {
    "from": {"name": "Oeschinensee", "latLng": [46.49836, 7.72667]},
    "to": {"name": "Blüemlisalphütte", "latLng": [46.51019, 7.77162]},
}

LIVE_FIXTURES = {
    "profile.json": "swissalti_profile_oeschinensee",
    "overpass": "overpass_sac_oeschinensee",
    "MapServer/identify": "swissnames3d_oeschinensee",
    "SearchServer": "geoadmin_search_oeschinensee",
}


@pytest.fixture
def live_client(tmp_path):
    settings = Settings(
        source_mode="live",
        cache_dir=tmp_path / "cache",
        trails_db=FIXTURES / "trails_oeschinensee.sqlite",
        http_backoff_s=0.0,
    )
    client = CachedHttpClient(settings, transport=replay_by_url(LIVE_FIXTURES))
    elevation = SwissAltiElevationSource(settings, client)
    sources = Sources(
        mode="live",
        routes=TlmRouteSource(
            settings,
            client,
            elevation=elevation,
            grades=OverpassGradeSource(settings, client),
            names=SwissNamesSource(settings, client),
        ),
        elevation=elevation,
        weather=NotImplementedWeatherSource(),
        warnings=NotImplementedWarningSource(),
        assessor=NotImplementedAssessor(),
    )

    app = create_app(frontend_dist=tmp_path)
    app.dependency_overrides[get_sources] = lambda: sources
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_reports_live_mode(live_client):
    assert live_client.get("/api/health").json() == {"status": "ok", "mode": "live"}


def test_search_returns_places_not_addresses(live_client):
    response = live_client.get("/api/routes/search", params={"q": "Oeschinensee"})

    assert response.status_code == 200
    hits = response.json()
    assert hits, "the recorded response should yield at least the lake"
    assert all({"name", "latLng", "rank"} == set(hit) for hit in hits)
    assert all("<" not in hit["name"] for hit in hits)


def test_search_is_not_mistaken_for_a_route_id(live_client):
    """`/routes/search` is registered above `/routes/{route_id}`; the wrong order 404s here."""
    assert live_client.get("/api/routes/search", params={"q": "Oeschinensee"}).status_code == 200


def test_a_route_is_computed_and_then_fetchable_by_its_id(live_client):
    created = live_client.post("/api/routes", json=BODY)
    assert created.status_code == 200
    route = created.json()

    fetched = live_client.get(f"/api/routes/{route['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == route


def test_the_same_request_twice_is_the_same_route(live_client):
    first = live_client.post("/api/routes", json=BODY).json()
    second = live_client.post("/api/routes", json=BODY).json()

    assert first["id"] == second["id"]
    assert first == second


def test_the_computed_route_is_the_shape_the_frontend_reads(live_client):
    route = live_client.post("/api/routes", json=BODY).json()

    assert route["fromName"] == "Oeschinensee"
    assert route["toName"] == "Blüemlisalphütte"
    # Camel case on the wire, and unset optional fields omitted rather than sent as null.
    assert route["cruxStopId"].startswith("hohturli")
    assert "null" not in str(route.values())
    assert route["stops"][0]["legMinutes"] == 0
    assert len(route["geometry"]) == len(route["elevations"])
    assert all(leg["toIndex"] < len(route["geometry"]) for leg in route["legs"])


def test_the_computed_route_agrees_with_the_hand_authored_one(live_client):
    """The numbers `mock_data.py` typed in, arrived at from swisstopo data instead.

    Loose bounds on purpose: this is a sanity floor that catches a broken clip, a wrong projection
    or a mangled profile, not a regression lock on the exact figures.
    """
    route = live_client.post("/api/routes", json=BODY).json()

    assert 9 < route["distanceKm"] < 13  # hand-authored: 11.2
    assert 1000 < route["ascentM"] < 1400  # hand-authored: 1220
    assert route["bailoutName"] == "Berghaus Oberbärgli"  # hand-authored: "Oberbärgli"

    day = sum(stop["legMinutes"] for stop in route["stops"])
    day += sum(stop.get("breakMinutes", 0) for stop in route["stops"])
    assert 400 < day < 600  # hand-authored: 490


def test_an_unroutable_request_is_503_naming_the_source(live_client):
    response = live_client.post(
        "/api/routes",
        json={**BODY, "to": {"name": "Bern", "latLng": [46.9480, 7.4474]}},
    )

    assert response.status_code == 503
    assert response.json()["source"] == "swisstlm3d"


def test_a_route_id_that_was_never_computed_is_404(live_client):
    response = live_client.get("/api/routes/rdeadbeefdeadbeef")

    assert response.status_code == 404
    # The message has to say what to do about it: the frontend shows this state to a hiker.
    assert "search for it again" in response.json()["detail"]


def test_phase_two_sources_still_fail_loudly(live_client):
    route = live_client.post("/api/routes", json=BODY).json()

    response = live_client.get(f"/api/routes/{route['id']}/assessment")

    assert response.status_code == 503
    assert "Phase 3" in response.json()["detail"]


def test_a_failing_grade_lookup_costs_detail_not_the_route(tmp_path):
    """Overpass is rate-limited and sometimes down. That must not cost the hiker the route."""
    settings = Settings(
        source_mode="live",
        cache_dir=tmp_path / "cache",
        trails_db=FIXTURES / "trails_oeschinensee.sqlite",
        http_backoff_s=0.0,
    )
    # Every request replays the elevation profile, so Overpass and swissnames3d get a body they
    # cannot parse and raise `SourceUnavailable`.
    client = CachedHttpClient(settings, transport=replay("swissalti_profile_oeschinensee"))
    elevation = SwissAltiElevationSource(settings, client)
    sources = Sources(
        mode="live",
        routes=TlmRouteSource(
            settings,
            client,
            elevation=elevation,
            grades=OverpassGradeSource(settings, client),
            names=SwissNamesSource(settings, client),
        ),
        elevation=elevation,
        weather=NotImplementedWeatherSource(),
        warnings=NotImplementedWarningSource(),
        assessor=NotImplementedAssessor(),
    )
    app = create_app(frontend_dist=tmp_path)
    app.dependency_overrides[get_sources] = lambda: sources

    with TestClient(app) as test_client:
        response = test_client.post("/api/routes", json=BODY)

    assert response.status_code == 200
    route = response.json()
    # Still a walkable route, graded by swisstopo's own class and flagged as an estimate.
    assert route["stops"][0]["legMinutes"] == 0
    assert all(leg["gradeEstimated"] for leg in route["legs"])
