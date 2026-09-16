"""The demo sources: today's hand-authored data, behind the protocols.

`mock_data.py` is left exactly as it was — it is pure data, and keeping the adapter separate from
it means `SOURCE_MODE=demo` provably serves the same bytes as before this seam existed.
"""

from ..domain import ElevationProfile, GeoPoint, PlaceHit, PointForecast, Warning
from ..mock_data import FORECAST, RECENT_ROUTES, ROUTES, get_assessment
from ..models import AssessmentData, RecentRoute, Route, Scenario

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

    async def recent_routes(self) -> list[RecentRoute]:
        return RECENT_ROUTES


class DemoElevationSource:
    """Demo waypoints already carry their elevation; unknown points stay unknown."""

    async def profile(self, points: list[GeoPoint]) -> ElevationProfile:
        return ElevationProfile(points=tuple(points))


class DemoWeatherSource:
    """One forecast, from `mock_data.FORECAST`. In demo mode the hazards are the authored truth."""

    async def forecast_at(self, point: GeoPoint, hour: int) -> PointForecast:
        return PointForecast(model_run=DEMO_MODEL_RUN, hour=hour, temp_c=FORECAST.feels_like_c)


class DemoWarningSource:
    """No warnings data, which is why `warnings` is one of the authored gaps."""

    async def warnings_for(self, points: list[GeoPoint]) -> list[Warning]:
        return []


class DemoAssessor:
    """The authored hazards, picked by scenario. Phase 3's engine replaces exactly this."""

    async def assess(self, route: Route, scenario: Scenario) -> AssessmentData:
        return get_assessment(scenario)
