"""The seams. Every later phase implements one of these protocols; nothing above them changes.

A source parses and returns domain objects, never a raw payload: whether the forecast arrived as
GRIB2 or JSON is the source's problem, and stops there.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..domain import ElevationProfile, GeoPoint, PlaceHit, PointForecast, Warning
from ..models import AssessmentData, RecentRoute, Route, Scenario


class SourceUnavailable(Exception):
    """A source could not answer: unreachable, unparseable, or not implemented yet.

    The single failure type the API maps onto `not_assessable` or a specific gap, so degradation
    is honest rather than silent.
    """

    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason


@runtime_checkable
class RouteSource(Protocol):
    """Where a route comes from: hand-authored today, swissTLM3D in Phase 1."""

    async def search(self, query: str) -> list[PlaceHit]: ...

    async def get_route(self, route_id: str) -> Route | None: ...

    async def recent_routes(self) -> list[RecentRoute]: ...


@runtime_checkable
class ElevationSource(Protocol):
    async def profile(self, points: list[GeoPoint]) -> ElevationProfile: ...


@runtime_checkable
class WeatherSource(Protocol):
    """Implemented twice in Phase 2 (ICON GRIB2 and Open-Meteo), switched by `SOURCE_MODE`."""

    async def forecast_at(self, point: GeoPoint, hour: int) -> PointForecast: ...


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
