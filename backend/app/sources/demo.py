"""The demo sources: today's hand-authored data, behind the protocols.

`mock_data.py` is left exactly as it was — it is pure data, and keeping the adapter separate from
it means `SOURCE_MODE=demo` provably serves the same bytes as before this seam existed.
"""

from datetime import date, datetime

from ..domain import ElevationProfile, GeoPoint, ModelRun, PlaceHit, PointForecast, Warning
from ..mock_data import FORECAST, RECENT_ROUTES, ROUTES, get_assessment
from ..models import AssessmentData, RecentRoute, Route, RouteRequest, Scenario
from .base import SourceUnavailable
from .weather_common import ICON_CH1, SWISS_TIME, local_today

# `mock_data.FORECAST` records the run as a model name and an issue time in minutes.
DEMO_MODEL_RUN = f"{FORECAST.model} {FORECAST.issued_at // 60:02d}:{FORECAST.issued_at % 60:02d}"


class DemoRouteSource:
    """The one showcase route, matched by name so the Phase 4 route picker has something to call."""

    async def search(self, query: str) -> list[PlaceHit]:
        needle = query.casefold().strip()
        hits = []
        for route in ROUTES.values():
            for rank, waypoint in enumerate(route.waypoints):
                if needle and needle in waypoint.name.casefold():
                    lat, lng = waypoint.lat_lng
                    hits.append(PlaceHit(waypoint.name, GeoPoint(lat, lng, waypoint.elevation_m), rank))
        return hits

    async def get_route(self, route_id: str) -> Route | None:
        return ROUTES.get(route_id)

    async def create_route(self, request: RouteRequest) -> Route:
        # Demo mode has no trail network to route over, and inventing a line between two arbitrary
        # points is exactly the kind of made-up data this mode exists to keep honest.
        raise SourceUnavailable("demo", "routing needs SOURCE_MODE=live and an imported trail graph")

    async def recent_routes(self) -> list[RecentRoute]:
        return RECENT_ROUTES


class DemoElevationSource:
    """Demo waypoints already carry their elevation; unknown points stay unknown."""

    async def profile(self, points: list[GeoPoint]) -> ElevationProfile:
        return ElevationProfile(points=tuple(points))


class DemoWeatherSource:
    """One forecast, from `mock_data.FORECAST`. In demo mode the hazards are the authored truth."""

    async def forecast_at(self, point: GeoPoint, hour: int, day: date | None = None) -> PointForecast:
        return PointForecast(model_run=DEMO_MODEL_RUN, hour=hour, temp_c=FORECAST.feels_like_c)

    async def latest_run(self, day: date | None = None) -> ModelRun:
        """The authored issue time, today: the demo forecast is always this morning's."""
        day = day or local_today()
        hours, minutes = divmod(FORECAST.issued_at, 60)
        issued = datetime(day.year, day.month, day.day, hours, minutes, tzinfo=SWISS_TIME)
        return ModelRun(FORECAST.model, issued, ICON_CH1.horizon_h)


class DemoWarningSource:
    """No warnings data, which is why `warnings` is one of the authored gaps."""

    async def warnings_for(self, points: list[GeoPoint]) -> list[Warning]:
        return []


class DemoAssessor:
    """The authored hazards, picked by scenario. Phase 3's engine replaces exactly this."""

    async def assess(self, route: Route, scenario: Scenario) -> AssessmentData:
        return get_assessment(scenario)
