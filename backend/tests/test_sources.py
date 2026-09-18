"""The seams themselves: the built sources satisfy them and fail loudly."""

import ast
from pathlib import Path

import pytest

import app
from app.config import Settings
from app.domain import GeoPoint
from app.models import RouteRequest
from app.sources import build_sources
from app.sources.assessor import EngineAssessor
from app.sources.base import (
    Assessor,
    ElevationSource,
    Narrator,
    RouteSource,
    SourceUnavailable,
    WarningSource,
    WeatherSource,
)
from app.sources.grounded import GroundedAssessor
from app.sources.icon_grib import IconGribSource
from app.sources.openmeteo import OpenMeteoIconSource
from app.sources.swissalti import SwissAltiElevationSource
from app.sources.tlm import TlmRouteSource
from app.sources.warnings_app import AppWarningSource

pytestmark = pytest.mark.anyio


def test_the_built_sources_satisfy_the_protocols():
    live = build_sources(Settings())

    assert isinstance(live.narrator, Narrator)
    assert isinstance(live.routes, TlmRouteSource)
    assert isinstance(live.elevation, SwissAltiElevationSource)
    assert isinstance(live.routes, RouteSource)
    assert isinstance(live.elevation, ElevationSource)


def test_live_weather_is_grib_by_default_with_open_meteo_spread():
    live = build_sources(Settings())

    assert isinstance(live.weather, IconGribSource)
    assert isinstance(live.weather.spread, OpenMeteoIconSource)
    assert isinstance(live.weather, WeatherSource)
    assert isinstance(live.warnings, AppWarningSource)
    assert isinstance(live.warnings, WarningSource)


def test_one_setting_switches_weather_to_open_meteo():
    live = build_sources(Settings(weather_source="open-meteo"))

    assert isinstance(live.weather, OpenMeteoIconSource)


async def test_live_warnings_are_a_gap_unless_the_app_feed_is_enabled():
    live = build_sources(Settings())

    with pytest.raises(SourceUnavailable, match="METEOSWISS_APP_WARNINGS"):
        await live.warnings.warnings_for([GeoPoint(46.5, 7.7)])


def test_live_mode_runs_the_hazard_engine_over_the_configured_weather():
    live = build_sources(Settings(weather_source="open-meteo"))

    assert isinstance(live.assessor, GroundedAssessor)
    assert isinstance(live.assessor, Assessor)
    engine = live.assessor.inner
    assert isinstance(engine, EngineAssessor)
    assert engine.weather is live.weather
    assert engine.warnings is live.warnings


@pytest.mark.parametrize("package", ["routing", "hazards", "guidance", "narration", "ask"])
def test_pure_layers_import_nothing_from_sources(package):
    """`routing/`, `hazards/`, `guidance/` and `narration/` decide; `sources/` fetches. The import graph keeps it so."""
    root = Path(app.__file__).parent / package
    offending = []
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and "sources" in node.module.split("."):
                offending.append(f"{path.name}: from {'.' * node.level}{node.module}")
    assert offending == []


async def test_live_routing_without_an_imported_graph_says_how_to_build_it(tmp_path):
    # `cache_dir` is isolated deliberately: a computed route is cached by id, so pointing at the
    # real cache would answer from it and never reach the missing graph this test is about.
    live = build_sources(Settings(trails_db=tmp_path / "absent.sqlite", cache_dir=tmp_path / "cache"))

    with pytest.raises(SourceUnavailable, match="import_trails"):
        await live.routes.create_route(
            RouteRequest.model_validate(
                {
                    "from": {"name": "Oeschinensee", "latLng": [46.49836, 7.72667]},
                    "to": {"name": "Blüemlisalphütte", "latLng": [46.51019, 7.77162]},
                }
            )
        )
