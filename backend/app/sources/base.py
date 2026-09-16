"""The seams. Every later phase implements one of these protocols; nothing above them changes.

A source parses and returns domain objects, never a raw payload: whether the forecast arrived as
GRIB2 or JSON is the source's problem, and stops there.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from ..domain import ElevationProfile, GeoPoint, ModelRun, PlaceHit, PointForecast, Warning
from ..errors import SourceUnavailable
from ..models import AssessmentData, RecentRoute, Route, RouteRequest, Scenario

__all__ = [
    "Assessor",
    "ElevationSource",
    "RouteSource",
    "SourceUnavailable",
    "Sources",
    "WarningSource",
    "WeatherSource",
]


@runtime_checkable
class RouteSource(Protocol):
    """Where a route comes from: hand-authored today, swissTLM3D in Phase 1."""

    async def search(self, query: str) -> list[PlaceHit]: ...

    async def get_route(self, route_id: str) -> Route | None: ...

    async def create_route(self, request: RouteRequest) -> Route: ...

    async def recent_routes(self) -> list[RecentRoute]: ...


@runtime_checkable
class ElevationSource(Protocol):
    async def profile(self, points: list[GeoPoint]) -> ElevationProfile: ...


@runtime_checkable
class WeatherSource(Protocol):
    """Implemented twice: ICON GRIB2 from MeteoSwiss and the same model over Open-Meteo's JSON.

    `hour` is minutes since local midnight (Europe/Zurich), like every time on the wire, and is
    floored to the hour. `day` defaults to today there. Which model answers — ICON-CH1 for the
    next 33 hours, ICON-CH2 beyond — is the source's decision, reported in `model_run`.
    """

    async def forecast_at(self, point: GeoPoint, hour: int, day: date | None = None) -> PointForecast: ...

    async def latest_run(self, day: date | None = None) -> ModelRun:
        """The newest run that covers `day`: the real `issuedAt` behind the stale banner."""
        ...


@runtime_checkable
class WarningSource(Protocol):
    async def warnings_for(self, points: list[GeoPoint]) -> list[Warning]: ...


@runtime_checkable
class Assessor(Protocol):
    """Terrain x forecast x arrival hour -> hazards. Phase 3's engine replaces the demo one.

    `scenario` only means anything under `SOURCE_MODE=demo`, where it picks one of the four
    demo states; a real assessor derives the outcome and ignores it.
    """

    async def assess(self, route: Route, scenario: Scenario) -> AssessmentData: ...


@dataclass(frozen=True, slots=True)
class Sources:
    """Everything the API layer is allowed to know about where data comes from."""

    mode: str
    routes: RouteSource
    elevation: ElevationSource
    weather: WeatherSource
    warnings: WarningSource
    assessor: Assessor
