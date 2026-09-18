from dataclasses import replace

import pytest
from authored import authored_sources
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.sources import get_sources

ROUTE_ID = "oeschinensee-bluemlisalphuette"


@pytest.fixture
def client(tmp_path):
    """The API over the authored test sources. An empty dist dir: API only, no frontend."""
    app = create_app(frontend_dist=tmp_path)
    sources = authored_sources(Settings(cache_dir=tmp_path / "cache"))
    app.dependency_overrides[get_sources] = lambda: sources
    return TestClient(app)


def assessment(client):
    response = client.get(f"/api/routes/{ROUTE_ID}/assessment")
    assert response.status_code == 200
    return response.json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_route_uses_camel_case_and_omits_unset_fields(client):
    route = client.get(f"/api/routes/{ROUTE_ID}").json()
    assert route["cruxStopId"] == "hohturli"
    assert route["waypoints"][0]["latLng"] == [46.4985, 7.728]
    assert route["stops"][4]["breakMinutes"] == 45
    assert "breakMinutes" not in route["stops"][0]


def test_unknown_route_is_404(client):
    assert client.get("/api/routes/nope").status_code == 404
    assert client.get("/api/routes/nope/assessment").status_code == 404


def test_recent_routes_are_kept_on_the_device_not_served(client):
    # There is no user on the server, so there is nobody's history to serve.
    assert client.get("/api/recent-routes").status_code == 404


def test_hazards_carry_their_figures_as_facts(client):
    gusts, showers = assessment(client)["hazards"]
    assert gusts["facts"] == {"gustKmh": 60, "thresholdKmh": 40, "elevationM": 2778}
    assert showers["facts"] == {"precipMm": 1.2, "thresholdMm": 0.5, "freezingLevelM": 2900}


def test_the_assessment_is_camel_case_with_explicit_intervals(client):
    data = assessment(client)
    assert data["outcome"] == "assessed"
    assert data["stale"] is False
    assert [h["id"] for h in data["hazards"]] == ["gusts-hohturli", "showers-descent"]
    assert data["hazards"][0]["window"] == {"from": 660, "to": 840}
    # The authored build-up is now an explicit interval rather than a separate field.
    assert data["hazards"][0]["stops"]["hohturli"] == [
        {"from": 630, "to": 660, "severity": "mod"},
        {"from": 660, "to": 840, "severity": "high"},
    ]
    assert "buildUpFrom" not in data["hazards"][0]


def test_conditions_carry_the_authored_crux_figures(client):
    conditions = assessment(client)["conditions"]["hohturli"]
    at_noon = next(row for row in conditions if row["from"] <= 720 < row["to"])
    assert at_noon == {"from": 660, "to": 840, "gustKmh": 55, "feelsLikeC": -2}


def test_the_assessment_accepts_a_date(client):
    response = client.get(f"/api/routes/{ROUTE_ID}/assessment", params={"date": "2026-09-19"})
    assert response.status_code == 200
    assert client.get(f"/api/routes/{ROUTE_ID}/assessment", params={"date": "Saturday"}).status_code == 422


def test_retry_reports_source_still_down(client):
    result = client.post("/api/forecast/retry").json()
    assert result["available"] is False
    assert 0 <= result["checkedAt"] < 24 * 60


def test_serves_frontend_with_spa_fallback(tmp_path):
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    client = TestClient(create_app(frontend_dist=tmp_path))

    assert client.get("/").text == "<div id=root></div>"
    assert client.get("/assessment/map").text == "<div id=root></div>"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/api/health").json()["status"] == "ok"

    missing_api = client.get("/api/nope")
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"] == "application/json"


def test_hazard_provenance_cites_the_guidance_it_is_grounded_in(client):
    gusts, showers = assessment(client)["hazards"]
    assert gusts["provenance"].endswith(" · SAC hiking scale")
    assert showers["provenance"].endswith(" · SAC hiking scale")


def test_narration_without_a_model_still_cites_its_guidance(client):
    response = client.get(f"/api/routes/{ROUTE_ID}/narration", params={"lang": "fr"})

    assert response.status_code == 200
    narration = response.json()
    assert narration["enabled"] is False and "model" not in narration
    assert [h["id"] for h in narration["hazards"]] == ["gusts-hohturli", "showers-descent"]
    assert all("body" not in h for h in narration["hazards"])
    assert narration["hazards"][0]["citations"][0]["url"].startswith("https://www.sac-cas.ch/")


def test_narration_follows_the_route(client):
    assert client.get("/api/routes/nope/narration").status_code == 404
    assert client.get(f"/api/routes/{ROUTE_ID}/narration", params={"lang": "de"}).status_code == 422


def test_the_mcp_server_answers_at_mcp_next_to_the_frontend(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>")
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    hello = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
    }
    # As a context manager, so the lifespan runs the MCP session manager.
    with TestClient(create_app(frontend_dist=tmp_path)) as served:
        response = served.post("/mcp", headers=headers, json=hello)
        assert response.status_code == 200
        assert '"name":"hiking-safety-assistant"' in response.text
        # Not swallowed by the frontend's client-side routing fallback.
        assert served.get("/mcp/anything").status_code == 404
        assert served.get("/some/page").status_code == 200


def test_an_unexpected_error_is_json_with_a_source(tmp_path):
    """Whatever breaks, the client gets the shape its `ApiError` reads, never an HTML page."""

    class Broken:
        async def search(self, q):
            raise RuntimeError("bug")

    app = create_app(frontend_dist=tmp_path)
    sources = get_sources()
    app.dependency_overrides[get_sources] = lambda: replace(sources, routes=Broken())
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/routes/search", params={"q": "x"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal error", "source": "internal"}
