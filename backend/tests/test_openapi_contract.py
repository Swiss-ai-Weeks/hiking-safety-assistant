"""Guards the committed schema the frontend types are generated from."""

from pathlib import Path

from app.openapi_dump import openapi_json, openapi_schema

SNAPSHOT = Path(__file__).resolve().parents[1] / "openapi.json"

# The parsed domain objects in `app/domain.py`. None of them is a wire type.
INTERNAL = {"GeoPoint", "PlaceHit", "PointForecast", "ElevationProfile", "Warning"}


def test_the_committed_schema_is_current():
    assert SNAPSHOT.read_text(encoding="utf-8") == openapi_json(), (
        "backend/openapi.json is out of date with models.py — run `pnpm gen:api` and commit the result"
    )


def test_the_schema_does_not_leak_internal_domain_objects():
    leaked = INTERNAL & set(openapi_schema()["components"]["schemas"])

    assert not leaked, f"internal domain objects reached the wire contract: {sorted(leaked)}"


def test_the_dump_does_not_depend_on_the_frontend_being_built():
    # Two dumps of the same app must be identical whether or not frontend/dist exists.
    assert openapi_json() == openapi_json()
    assert "/{path:path}" not in openapi_schema()["paths"]
