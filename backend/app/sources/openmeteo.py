"""MeteoSwiss ICON over Open-Meteo's JSON: the same model fields, no GRIB toolchain.

This is the fallback that keeps demo day alive if eccodes will not install, and also where
ensemble spread comes from for both sources. Downloading ten perturbed members as GRIB costs
23 MB per variable per hour; Open-Meteo serves the same members as a few kilobytes of JSON.

Open-Meteo downscales to the `elevation` it is given, so a stop's temperature is already
carried from the model's smoothed terrain to the real one.
"""

import logging
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

from ..config import Settings
from ..domain import GeoPoint, ModelRun, PointForecast
from ..errors import SourceUnavailable
from .http import CachedHttpClient, CacheKey
from .weather_common import (
    THUNDER_CAPE_JKG,
    IconModel,
    floor_hour,
    fraction_at_least,
    local_today,
    model_for,
    percentile,
    target_time,
)

log = logging.getLogger(__name__)

SOURCE = "open-meteo"

# Open-Meteo name -> `PointForecast` field. Precipitation and gusts are both over the preceding
# hour, matching ICON's own TOT_PREC difference and VMAX_10M.
HOURLY_FIELDS = {
    "temperature_2m": "temp_c",
    "dew_point_2m": "dewpoint_c",
    "wind_speed_10m": "wind_kmh",
    "wind_gusts_10m": "gust_kmh",
    "precipitation": "precip_mm",
    "cape": "cape_jkg",
    "cloud_base": "cloud_base_m",
    "freezing_level_height": "freezing_level_m",
    "snowfall_height": "snowline_m",
}
ENSEMBLE_FIELDS = ("wind_gusts_10m", "precipitation", "cape")


def parse_meta(payload: Any, model: IconModel) -> ModelRun:
    initialised = payload.get("last_run_initialisation_time") if isinstance(payload, dict) else None
    if not isinstance(initialised, int | float):
        raise SourceUnavailable(SOURCE, f"{model.open_meteo} metadata has no last_run_initialisation_time")
    return ModelRun(model.name, datetime.fromtimestamp(initialised, UTC), model.horizon_h)


def _hour_index(payload: Any, day: date, hour: int) -> tuple[dict[str, Any], int]:
    hourly = payload.get("hourly") if isinstance(payload, dict) else None
    if not isinstance(hourly, dict) or not isinstance(hourly.get("time"), list):
        reason = payload.get("reason") if isinstance(payload, dict) else None
        raise SourceUnavailable(SOURCE, reason or "response has no hourly series")
    stamp = f"{day.isoformat()}T{floor_hour(hour) // 60:02d}:00"
    try:
        return hourly, hourly["time"].index(stamp)
    except ValueError:
        raise SourceUnavailable(SOURCE, f"no forecast for {stamp}") from None


def _value(series: Any, index: int) -> float | None:
    if not isinstance(series, list) or index >= len(series) or series[index] is None:
        return None
    return float(series[index])


def parse_forecast(payload: Any, day: date, hour: int, model_run: str) -> PointForecast:
    hourly, index = _hour_index(payload, day, hour)
    values = {field: _value(hourly.get(name), index) for name, field in HOURLY_FIELDS.items()}
    return PointForecast(model_run=model_run, hour=floor_hour(hour), **values)


def parse_ensemble(payload: Any, day: date, hour: int) -> dict[str, float | None]:
    """Spread across the control run and every perturbed member, as `PointForecast` fields."""
    hourly, index = _hour_index(payload, day, hour)

    def members(name: str) -> list[float]:
        # `wind_gusts_10m` is the control, `wind_gusts_10m_member01`... the perturbed members.
        keys = [key for key in hourly if key == name or key.startswith(f"{name}_member")]
        return [value for key in keys if (value := _value(hourly[key], index)) is not None]

    gusts, precip, cape = (members(name) for name in ENSEMBLE_FIELDS)
    if not gusts and not precip:
        raise SourceUnavailable(SOURCE, "ensemble response carried no members")
    return {
        "gust_kmh_p10": percentile(gusts, 10),
        "gust_kmh_p90": percentile(gusts, 90),
        "precip_mm_p10": percentile(precip, 10),
        "precip_mm_p90": percentile(precip, 90),
        "thunder_probability": fraction_at_least(cape, THUNDER_CAPE_JKG),
    }


class OpenMeteoIconSource:
    def __init__(self, settings: Settings, client: CachedHttpClient) -> None:
        self.settings = settings
        self.client = client

    def _common(self, point: GeoPoint, day: date) -> dict[str, str]:
        params = {
            "latitude": f"{point.lat:.4f}",
            "longitude": f"{point.lng:.4f}",
            "timezone": "Europe/Zurich",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
        }
        if point.elevation_m is not None:
            params["elevation"] = str(round(point.elevation_m))
        if self.settings.open_meteo_api_key:
            params["apikey"] = self.settings.open_meteo_api_key
        return params

    def forecast_params(self, model: IconModel, point: GeoPoint, day: date) -> dict[str, str]:
        """The query. Separate from the call so the fixture recorder sends the same request."""
        return {**self._common(point, day), "hourly": ",".join(HOURLY_FIELDS), "models": model.open_meteo}

    def ensemble_params(self, model: IconModel, point: GeoPoint, day: date) -> dict[str, str]:
        return {
            **self._common(point, day),
            "hourly": ",".join(ENSEMBLE_FIELDS),
            "models": model.open_meteo_ensemble,
        }

    def meta_url(self, model: IconModel) -> str:
        return f"{self.settings.open_meteo_meta_url}/{model.open_meteo}/static/meta.json"

    async def run_of(self, model: IconModel) -> ModelRun:
        payload = await self.client.get_json(
            self.meta_url(model),
            key=CacheKey(source=SOURCE, endpoint="meta", params={"model": model.open_meteo}),
            ttl_s=self.settings.cache_ttl_run_s,
        )
        return parse_meta(payload, model)

    async def latest_run(self, day: date | None = None) -> ModelRun:
        day = day or local_today()
        return await self.run_of(model_for(target_time(12 * 60, day)))

    async def forecast_at(self, point: GeoPoint, hour: int, day: date | None = None) -> PointForecast:
        day = day or local_today()
        model = model_for(target_time(hour, day))
        run = await self.run_of(model)

        # One request per stop per day, keyed by run: every other hour of the same stop is a hit,
        # and a new run is a miss without waiting for a TTL.
        payload = await self.client.get_json(
            f"{self.settings.open_meteo_base_url}/forecast",
            key=CacheKey(
                source=SOURCE, endpoint="forecast", point=point, model_run=run.label, params={"day": str(day)}
            ),
            ttl_s=self.settings.cache_ttl_forecast_s,
            params=self.forecast_params(model, point, day),
        )
        forecast = parse_forecast(payload, day, hour, run.label)

        spread = await self.ensemble_at(point, hour, day)
        return replace(forecast, **spread) if spread else forecast

    async def ensemble_at(self, point: GeoPoint, hour: int, day: date | None = None) -> dict[str, float | None]:
        """Spread for one stop and hour, or `{}` when the ensemble cannot answer.

        Missing spread is not an error: the control run still stands, and the assessment reads
        the absence as a reason to be partial rather than confident.
        """
        day = day or local_today()
        model = model_for(target_time(hour, day))
        try:
            run = await self.run_of(model)
            payload = await self.client.get_json(
                f"{self.settings.open_meteo_ensemble_url}/ensemble",
                key=CacheKey(
                    source=SOURCE, endpoint="ensemble", point=point, model_run=run.label, params={"day": str(day)}
                ),
                ttl_s=self.settings.cache_ttl_forecast_s,
                params=self.ensemble_params(model, point, day),
            )
            return parse_ensemble(payload, day, hour)
        except SourceUnavailable as exc:
            log.warning("no ensemble spread for %s at %s: %s", point, hour, exc)
            return {}
