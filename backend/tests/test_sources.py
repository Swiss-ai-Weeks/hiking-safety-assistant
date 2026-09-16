"""The seams themselves: demo satisfies them, live is selectable and fails loudly."""

import pytest

from app.config import Settings
from app.domain import GeoPoint
from app.mock_data import OESCHINEN_ROUTE, get_assessment
from app.sources import build_sources
from app.sources.base import (
    Assessor,
    ElevationSource,
    RouteSource,
    SourceUnavailable,
    WarningSource,
    WeatherSource,
)
from app.sources.geoadmin import GeoAdminRouteSource

pytestmark = pytest.mark.anyio

DEMO = build_sources(Settings(source_mode="demo"))
SCENARIOS = ["assessed", "partial", "not_assessable", "stale"]


def test_demo_sources_satisfy_the_protocols():
    assert isinstance(DEMO.routes, RouteSource)
    assert isinstance(DEMO.elevation, ElevationSource)
    assert isinstance(DEMO.weather, WeatherSource)
    assert isinstance(DEMO.warnings, WarningSource)
    assert isinstance(DEMO.assessor, Assessor)


async def test_demo_route_source_serves_the_showcase_route():
    assert await DEMO.routes.get_route(OESCHINEN_ROUTE.id) is OESCHINEN_ROUTE
    assert await DEMO.routes.get_route("nope") is None
    assert [r.id for r in await DEMO.routes.recent_routes()] == ["schynige-platte-faulhorn", "gemmipass"]


@pytest.mark.parametrize("scenario", SCENARIOS)
async def test_demo_assessor_still_serves_every_scenario(scenario):
    assert await DEMO.assessor.assess(OESCHINEN_ROUTE, scenario) == get_assessment(scenario)


async def test_demo_search_matches_waypoints_by_name():
    hits = await DEMO.routes.search("TÜRLI")

    assert [hit.name for hit in hits] == ["Hohtürli"]
    assert hits[0].point.elevation_m == 2778
    assert await DEMO.routes.search("nowhere") == []


async def test_demo_weather_reports_the_run_it_came_from():
    forecast = await DEMO.weather.forecast_at(GeoPoint(46.4888, 7.7717, 2778), hour=11 * 60)

    assert forecast.model_run == "ICON-CH1 06:40"
    assert forecast.hour == 11 * 60
    # Demo has no gust field: the authored hazards carry that, not the forecast.
    assert forecast.gust_kmh is None


async def test_demo_elevation_keeps_what_it_was_given():
    points = [GeoPoint(46.4985, 7.728, 1578), GeoPoint(46.4888, 7.7717, 2778)]

    profile = await DEMO.elevation.profile(points)

    assert profile.ascent_m == 1200
    assert profile.descent_m == 0


async def test_demo_has_no_warnings_which_is_why_it_is_a_gap():
    assert await DEMO.warnings.warnings_for([]) == []
    # The empty list is honest rather than reassuring: the authored gaps say `warnings` is missing.
    assert "warnings" in (await DEMO.assessor.assess(OESCHINEN_ROUTE, "assessed")).gaps


def test_live_mode_wires_the_real_search():
    live = build_sources(Settings(source_mode="live"))

    assert live.mode == "live"
    assert isinstance(live.routes, GeoAdminRouteSource)


@pytest.mark.parametrize(
    ("attribute", "call", "phase"),
    [
        ("elevation", lambda s: s.elevation.profile([]), "Phase 1"),
        ("weather", lambda s: s.weather.forecast_at(GeoPoint(46.5, 7.7), 600), "Phase 2"),
        ("warnings", lambda s: s.warnings.warnings_for([]), "Phase 2"),
        ("assessor", lambda s: s.assessor.assess(OESCHINEN_ROUTE, "assessed"), "Phase 3"),
    ],
)
async def test_unimplemented_live_sources_fail_loudly(attribute, call, phase):
    live = build_sources(Settings(source_mode="live"))

    with pytest.raises(SourceUnavailable, match=phase):
        await call(live)


async def test_live_routing_is_not_implemented_yet():
    live = build_sources(Settings(source_mode="live"))

    with pytest.raises(SourceUnavailable, match="Phase 1"):
        await live.routes.get_route(OESCHINEN_ROUTE.id)
