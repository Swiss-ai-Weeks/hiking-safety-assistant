import pytest
from fastapi.testclient import TestClient

from app import api
from app.main import create_app

ROUTE_ID = "oeschinensee-bluemlisalphuette"


@pytest.fixture
def client(tmp_path):
    # An empty dist dir: API only, no frontend.
    return TestClient(create_app(frontend_dist=tmp_path))


def assessment(client, scenario):
    response = client.get(f"/api/routes/{ROUTE_ID}/assessment", params={"scenario": scenario})
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


def test_recent_routes(client):
    recent = client.get("/api/recent-routes").json()
    assert [r["id"] for r in recent] == ["schynige-platte-faulhorn", "gemmipass"]
    assert recent[0]["checkedOn"] == "2026-09-06"


def test_assessed_scenario(client):
    data = assessment(client, "assessed")
    assert data["outcome"] == "assessed"
    assert data["stale"] is False
    assert [h["id"] for h in data["hazards"]] == ["gusts-hohturli", "showers-descent"]
    assert data["hazards"][0]["window"] == {"from": 660, "to": 840}


def test_partial_scenario_drops_gust_data(client):
    data = assessment(client, "partial")
    assert data["outcome"] == "partial"
    assert [h["kind"] for h in data["hazards"]] == ["showers"]
    assert [a["kind"] for a in data["alternatives"]] == ["altRoute"]
    assert data["notEvaluated"] == [{"legIds": ["moraine-hohturli", "hohturli-hutte"]}]


def test_not_assessable_has_no_hazards_or_recommendations(client):
    data = assessment(client, "not_assessable")
    assert data["outcome"] == "not_assessable"
    assert data["hazards"] == []
    assert data["alternatives"] == []


def test_stale_keeps_outcome(client):
    data = assessment(client, "stale")
    assert data["outcome"] == "assessed"
    assert data["stale"] is True


def test_invalid_scenario_is_rejected(client):
    response = client.get(f"/api/routes/{ROUTE_ID}/assessment", params={"scenario": "nonsense"})
    assert response.status_code == 422


def test_retry_reports_source_still_down(client, monkeypatch):
    monkeypatch.setattr(api, "RETRY_DELAY_S", 0)
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
    assert client.get("/api/health").json() == {"status": "ok"}

    missing_api = client.get("/api/nope")
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"] == "application/json"
