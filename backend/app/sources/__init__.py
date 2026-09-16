"""Picks the source implementations for the configured mode."""

import logging
from functools import lru_cache

from ..config import Settings, get_settings
from .base import (
    Assessor,
    ElevationSource,
    RouteSource,
    Sources,
    SourceUnavailable,
    WarningSource,
    WeatherSource,
)
from .demo import DemoAssessor, DemoElevationSource, DemoRouteSource, DemoWarningSource, DemoWeatherSource
from .http import CachedHttpClient
from .live import (
    NotImplementedAssessor,
    NotImplementedWarningSource,
    NotImplementedWeatherSource,
)
from .names import SwissNamesSource
from .osm import OverpassGradeSource
from .swissalti import SwissAltiElevationSource
from .tlm import TlmRouteSource

log = logging.getLogger(__name__)

__all__ = [
    "Assessor",
    "ElevationSource",
    "RouteSource",
    "SourceUnavailable",
    "Sources",
    "WarningSource",
    "WeatherSource",
    "build_sources",
    "get_sources",
]


def build_sources(settings: Settings) -> Sources:
    if settings.source_mode == "demo":
        return Sources(
            mode="demo",
            routes=DemoRouteSource(),
            elevation=DemoElevationSource(),
            weather=DemoWeatherSource(),
            warnings=DemoWarningSource(),
            assessor=DemoAssessor(),
        )

    client = CachedHttpClient(settings)
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
    log.warning(
        "SOURCE_MODE=live: routes and elevation are live, but %s are not implemented yet "
        "and will fail when called",
        ", ".join(
            f"{name} ({getattr(source, 'phase', '?')})"
            for name, source in (
                ("weather", sources.weather),
                ("warnings", sources.warnings),
                ("assessor", sources.assessor),
            )
            if hasattr(source, "phase")
        ),
    )
    return sources


@lru_cache
def get_sources() -> Sources:
    """FastAPI dependency. Cached so one process builds one set of sources (and one HTTP client)."""
    return build_sources(get_settings())
