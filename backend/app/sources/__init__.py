"""Builds the source implementations from the settings. Every one of them is real."""

import importlib.util
import logging
from functools import lru_cache

from ..config import Settings, get_settings
from .asker import LlmAsker
from .assessor import EngineAssessor
from .base import (
    Asker,
    Assessor,
    ElevationSource,
    Narrator,
    RouteSource,
    Sources,
    SourceUnavailable,
    WarningSource,
    WeatherSource,
)
from .grounded import GroundedAssessor
from .http import CachedHttpClient
from .icon_grib import IconGribSource
from .names import SwissNamesSource
from .narrator import LlmNarrator
from .openmeteo import OpenMeteoIconSource
from .osm import OverpassGradeSource
from .swissalti import SwissAltiElevationSource
from .tlm import TlmRouteSource
from .warnings_app import AppWarningSource

log = logging.getLogger(__name__)

__all__ = [
    "Asker",
    "Assessor",
    "ElevationSource",
    "Narrator",
    "RouteSource",
    "SourceUnavailable",
    "Sources",
    "WarningSource",
    "WeatherSource",
    "build_sources",
    "get_sources",
]


def build_sources(settings: Settings) -> Sources:
    client = CachedHttpClient(settings)
    elevation = SwissAltiElevationSource(settings, client)
    open_meteo = OpenMeteoIconSource(settings, client)
    # Ensemble spread comes from Open-Meteo either way: as GRIB it would be ten times the download.
    weather: WeatherSource = (
        IconGribSource(settings, client, spread=open_meteo) if settings.weather_source == "grib" else open_meteo
    )
    warnings = AppWarningSource(settings, client)
    sources = Sources(
        routes=TlmRouteSource(
            settings,
            client,
            elevation=elevation,
            grades=OverpassGradeSource(settings, client),
            names=SwissNamesSource(settings, client),
        ),
        elevation=elevation,
        weather=weather,
        warnings=warnings,
        assessor=GroundedAssessor(EngineAssessor(settings, client, weather, warnings)),
        narrator=LlmNarrator(settings, client.cache),
        asker=LlmAsker(settings, client.cache),
    )
    log.warning(
        "Sources: weather from %s, app warnings %s.",
        settings.weather_source,
        "on" if settings.meteoswiss_app_warnings else "off",
    )
    if settings.narration_enabled and not settings.narration_base_url:
        log.warning("NARRATION_ENABLED=true but NARRATION_BASE_URL is unset: hazards keep their templated copy")
    if settings.weather_source == "grib" and importlib.util.find_spec("eccodes") is None:
        log.warning(
            "WEATHER_SOURCE=grib but eccodes is not installed, so every forecast will fail: "
            "`uv sync --group grib`, or set WEATHER_SOURCE=open-meteo"
        )
    return sources


@lru_cache
def get_sources() -> Sources:
    """FastAPI dependency. Cached so one process builds one set of sources (and one HTTP client)."""
    return build_sources(get_settings())
