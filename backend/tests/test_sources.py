"""The seams themselves: demo satisfies them, live is selectable and fails loudly."""

import pytest

from app.config import Settings
from app.domain import GeoPoint
from app.mock_data import OESCHINEN_ROUTE, get_assessment
from app.models import RouteRequest
from app.sources import build_sources
from app.sources.base import (
    Assessor,
    ElevationSource,
    RouteSource,
    SourceUnavailable,
    WarningSource,
    WeatherSource,
)
from app.sources.icon_grib import IconGribSource
from app.sources.openmeteo import OpenMeteoIconSource
from app.sources.swissalti import SwissAltiElevationSource
from app.sources.tlm import TlmRouteSource
from app.sources.warnings_app import AppWarningSource
from app.sources.weather_common import SWISS_TIME

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


async def test_demo_mode_refuses_to_invent_a_route():
    # Demo has no trail network. Routing two arbitrary points would mean drawing a line, which is
    # the one thing this mode exists to avoid.
    with pytest.raises(SourceUnavailable, match="SOURCE_MODE=live"):
        await DEMO.routes.create_route(
            RouteRequest.model_validate(
                {"from": {"name": "a", "latLng": [46.5, 7.7]}, "to": {"name": "b", "latLng": [46.6, 7.8]}}
            )
        )


def test_live_mode_wires_routing_and_elevation():
    live = build_sources(Settings(source_mode="live"))

    assert live.mode == "live"
    assert isinstance(live.routes, TlmRouteSource)
    assert isinstance(live.elevation, SwissAltiElevationSource)
    assert isinstance(live.routes, RouteSource)
    assert isinstance(live.elevation, ElevationSource)


def test_live_weather_is_grib_by_default_with_open_meteo_spread():
    live = build_sources(Settings(source_mode="live"))

    assert isinstance(live.weather, IconGribSource)
    assert isinstance(live.weather.spread, OpenMeteoIconSource)
    assert isinstance(live.weather, WeatherSource)
    assert isinstance(live.warnings, AppWarningSource)
    assert isinstance(live.warnings, WarningSource)


def test_one_setting_switches_weather_to_open_meteo():
    live = build_sources(Settings(source_mode="live", weather_source="open-meteo"))

    assert isinstance(live.weather, OpenMeteoIconSource)


async def test_live_warnings_are_a_gap_unless_the_app_feed_is_enabled():
    live = build_sources(Settings(source_mode="live"))

    with pytest.raises(SourceUnavailable, match="METEOSWISS_APP_WARNINGS"):
        await live.warnings.warnings_for([GeoPoint(46.5, 7.7)])


async def test_the_hazard_engine_still_fails_loudly():
    live = build_sources(Settings(source_mode="live"))

    with pytest.raises(SourceUnavailable, match="Phase 3"):
        await live.assessor.assess(OESCHINEN_ROUTE, "assessed")


async def test_demo_weather_run_is_the_authored_issue_time():
    run = await DEMO.weather.latest_run()

    assert run.model == "ICON-CH1"
    assert run.reference_time.astimezone(SWISS_TIME).strftime("%H:%M") == "06:40"


async def test_live_routing_without_an_imported_graph_says_how_to_build_it(tmp_path):
    # `cache_dir` is isolated deliberately: a computed route is cached by id, so pointing at the
    # real cache would answer from it and never reach the missing graph this test is about.
    live = build_sources(
        Settings(source_mode="live", trails_db=tmp_path / "absent.sqlite", cache_dir=tmp_path / "cache")
    )

    with pytest.raises(SourceUnavailable, match="import_trails"):
        await live.routes.create_route(
            RouteRequest.model_validate(
                {
                    "from": {"name": "Oeschinensee", "latLng": [46.49836, 7.72667]},
                    "to": {"name": "Blüemlisalphütte", "latLng": [46.51019, 7.77162]},
                }
            )
        )
