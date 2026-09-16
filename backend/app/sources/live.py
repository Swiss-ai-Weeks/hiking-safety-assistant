"""Placeholders for the live sources later phases own.

Each one fails when called, naming the phase that implements it. Failing per source rather than
at startup is what lets Phases 1 and 2 land separately: a real `RouteSource` is usable while
`WeatherSource` is still missing.
"""

from ..domain import ElevationProfile, GeoPoint, PointForecast, Warning
from ..models import AssessmentData, Route, Scenario
from .base import SourceUnavailable


class NotImplementedElevationSource:
    phase = "Phase 1"

    async def profile(self, points: list[GeoPoint]) -> ElevationProfile:
        raise SourceUnavailable("swissalti3d", f"the elevation profile is not implemented yet ({self.phase})")


class NotImplementedWeatherSource:
    phase = "Phase 2"

    async def forecast_at(self, point: GeoPoint, hour: int) -> PointForecast:
        raise SourceUnavailable("icon", f"the MeteoSwiss forecast is not implemented yet ({self.phase})")


class NotImplementedWarningSource:
    phase = "Phase 2"

    async def warnings_for(self, points: list[GeoPoint]) -> list[Warning]:
        raise SourceUnavailable("meteoswiss-warnings", f"official warnings are not implemented yet ({self.phase})")


class NotImplementedAssessor:
    phase = "Phase 3"

    async def assess(self, route: Route, scenario: Scenario) -> AssessmentData:
        raise SourceUnavailable("hazards", f"the hazard engine is not implemented yet ({self.phase})")
