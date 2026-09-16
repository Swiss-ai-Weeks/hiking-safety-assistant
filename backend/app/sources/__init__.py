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
from .geoadmin import GeoAdminRouteSource
from .http import CachedHttpClient
from .live import (
    NotImplementedAssessor,
    NotImplementedElevationSource,
    NotImplementedWarningSource,
    NotImplementedWeatherSource,
)

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
    sources = Sources(
        mode="live",
        routes=GeoAdminRouteSource(settings, client),
        elevation=NotImplementedElevationSource(),
        weather=NotImplementedWeatherSource(),
        warnings=NotImplementedWarningSource(),
        assessor=NotImplementedAssessor(),
    )
    log.warning(
        "SOURCE_MODE=live: place search is live, but %s are not implemented yet and will fail when called",
        ", ".join(
            f"{name} ({getattr(source, 'phase', '?')})"
            for name, source in (
                ("elevation", sources.elevation),
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
