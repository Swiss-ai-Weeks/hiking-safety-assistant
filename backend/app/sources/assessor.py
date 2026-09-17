"""The live `Assessor`: fetch what the hazard engine needs, then let it decide.

All the I/O around `hazards/engine.py` lives here, and so does the mapping from failure to
outcome. A run that cannot be found is `not_assessable`; so is a day beyond every model's reach,
said as such. A single stop whose forecast failed costs that stop, not the assessment, and the
engine reports it as not evaluated. A warning feed that cannot answer is a gap.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime

from ..config import Settings
from ..domain import GeoPoint, PointForecast, Warning
from ..errors import SourceUnavailable
from ..hazards import engine
from ..models import AssessmentData, Route, Scenario
from .base import WarningSource, WeatherSource
from .http import CachedHttpClient, CacheKey
from .weather_common import local_today, model_for, target_time

log = logging.getLogger(__name__)

# Forecast requests in flight at once. The GRIB source downloads a file per variable per hour.
CONCURRENCY = 8
# Where `recheck` asks for a forecast: the question is whether the source answers at all, and Bern
# is inside every model's domain.
PROBE_POINT = GeoPoint(46.948, 7.447, 540)


class EngineAssessor:
    def __init__(
        self,
        settings: Settings,
        client: CachedHttpClient,
        weather: WeatherSource,
        warnings: WarningSource,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.settings = settings
        self.client = client
        self.weather = weather
        self.warnings = warnings
        self.now = now

    async def assess(self, route: Route, scenario: Scenario, day: date | None = None) -> AssessmentData:
        """`scenario` is a demo-mode control; the outcome here is derived, so it is ignored."""
        now = self.now()
        day = day or local_today(now)
        try:
            return await self._assess(route, day, now)
        except Exception:
            # A bug or an unexpected payload is still "we could not assess this", said as such, never a
            # 500 the briefing cannot render. Not cached, so the next request tries again.
            log.exception("assessment for %s on %s failed unexpectedly", route.id, day)
            return engine.not_assessable("source", now)

    async def _assess(self, route: Route, day: date, now: datetime) -> AssessmentData:

        try:
            model_for(target_time(engine.DAY_START, day), now)
        except SourceUnavailable as exc:
            log.info("assessment for %s: %s", day, exc)
            return engine.not_assessable("beyond_horizon", now)
        try:
            run = await self.weather.latest_run(day)
        except SourceUnavailable as exc:
            log.warning("no model run for %s: %s", day, exc)
            return engine.not_assessable("source", now)

        key = CacheKey(
            source="hazards",
            endpoint="assessment",
            model_run=run.label,
            params={"route": route.id, "day": day.isoformat(), "v": engine.ENGINE_VERSION},
        )
        ttl_s = min(self.settings.cache_ttl_forecast_s, self.settings.cache_ttl_warnings_s)
        if (cached := self.client.cache.read(key, ttl_s)) is not None:
            return AssessmentData.model_validate(cached)

        points = {waypoint.id: GeoPoint(*waypoint.lat_lng, float(waypoint.elevation_m)) for waypoint in route.waypoints}
        forecasts = await self._forecasts(points, day)
        warnings = await self._warnings(list(points.values()))

        data = engine.assess(route, forecasts, warnings, run, day, now)
        if data.outcome != "not_assessable":
            self.client.cache.write(key, data.model_dump(by_alias=True, exclude_none=True))
        return data

    async def recheck(self, day: date | None = None) -> bool:
        """Whether the forecast source answers again, for "Try again" on the not-assessable screen."""
        try:
            await self.weather.latest_run(day)
            await self.weather.forecast_at(PROBE_POINT, 12 * 60, day)
        except SourceUnavailable as exc:
            log.info("forecast still unavailable: %s", exc)
            return False
        except Exception:
            log.exception("forecast recheck failed unexpectedly")
            return False
        return True

    async def _forecasts(self, points: dict[str, GeoPoint], day: date) -> engine.Forecasts:
        gate = asyncio.Semaphore(CONCURRENCY)

        async def one(waypoint_id: str, hour: int) -> tuple[str, int, PointForecast | None]:
            async with gate:
                try:
                    return waypoint_id, hour, await self.weather.forecast_at(points[waypoint_id], hour, day)
                except SourceUnavailable as exc:
                    log.warning("no forecast for %s at %02d:00: %s", waypoint_id, hour // 60, exc)
                    return waypoint_id, hour, None

        results = await asyncio.gather(*(one(w, hour) for w in points for hour in engine.FORECAST_HOURS))
        forecasts: engine.Forecasts = {waypoint_id: {} for waypoint_id in points}
        for waypoint_id, hour, forecast in results:
            if forecast is not None:
                forecasts[waypoint_id][hour] = forecast
        return forecasts

    async def _warnings(self, points: list[GeoPoint]) -> list[Warning] | None:
        try:
            return await self.warnings.warnings_for(points)
        except SourceUnavailable as exc:
            log.info("warnings are a gap: %s", exc)
            return None
