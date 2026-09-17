"""MeteoSwiss ICON-CH1/CH2, read from the official GRIB2 files on the OGD STAC API.

Each forecast variable at each forecast hour is its own GRIB2 file — 2.3 MB for the control run,
23 MB for the ten-member ensemble — on ICON's native unstructured grid of ~1.1 million triangular
cells. So this source:

- reads the **control run only**; ensemble spread comes from Open-Meteo's JSON for the same
  members (see `openmeteo.py`), a few kilobytes instead of ten times this download;
- finds a stop's cell by nearest neighbour over the cell centres in the collection's
  `horizontal_constants` file, decoded once per process;
- keeps a run's downloaded messages on disk while that run is current (one file serves every stop
  at that hour) and deletes superseded runs, so the cache holds at most a couple of runs;
- caches the extracted per-point values under run + point + hour, which is all that is ever
  served — no grid leaves this module.

`eccodes` is imported lazily and lives in the optional `grib` dependency group. Without it the
source fails loudly per call, naming the switch to the JSON source.
"""

import asyncio
import logging
import math
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from ..config import Settings
from ..domain import GeoPoint, ModelRun, PointForecast
from ..errors import SourceUnavailable
from .http import COORD_DP, CachedHttpClient, CacheKey
from .weather_common import (
    KELVIN,
    MS_TO_KMH,
    IconModel,
    floor_hour,
    lapse_correct,
    local_today,
    model_for_day,
    target_time,
    wind_speed_kmh,
)

log = logging.getLogger(__name__)

SOURCE = "icon-grib"
SEARCH_PATH = "/search"

# What a hazard needs, and nothing else: of the ~100 variables per step, these ten.
GRIB_VARIABLES = (
    "T_2M",
    "TD_2M",
    "U_10M",
    "V_10M",
    "VMAX_10M",
    "TOT_PREC",
    "HZEROCL",
    "SNOWLMT",
    "CEILING",
    "CAPE_ML",
)

# ICON writes no bitmap; an undefined value (a snowfall limit when nothing falls) is this number.
MISSING = 9999.0

# Runs kept on disk per model: the current one, and the one before in case the current run is
# still being published and a step is missing from it.
KEEP_RUNS = 2


class Incomplete(Exception):
    """This run does not (yet) publish a message this forecast needs. Try the run before."""


# --- Pure parts: no eccodes, no network ------------------------------------------------------


def horizon_iso(hours: int) -> str:
    """STAC's `forecast:horizon` spelling: 27 h is "P1DT03H00M00S"."""
    days, rest = divmod(hours, 24)
    return f"P{days}DT{rest:02d}H00M00S"


def run_search(model: IconModel) -> dict[str, Any]:
    """Every run of `model` still published: a variable every run has, at step 0."""
    return {
        "collections": [model.stac_collection],
        "forecast:variable": "T_2M",
        "forecast:horizon": horizon_iso(0),
        "forecast:perturbed": False,
        # The API caps a page at 100 and pages no further. A day of CH1 runs is eight.
        "limit": 100,
    }


def message_search(model: IconModel, run: datetime, variable: str, hours: int) -> dict[str, Any]:
    """One variable at one step of one run. The API accepts one variable per search, not a list."""
    return {
        "collections": [model.stac_collection],
        "forecast:reference_datetime": f"{run.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}",
        "forecast:variable": variable,
        "forecast:horizon": horizon_iso(hours),
        "forecast:perturbed": False,
        "limit": 5,
    }


def _features(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise SourceUnavailable(SOURCE, "STAC search response has no `features` list")
    return [feature for feature in payload["features"] if isinstance(feature, dict)]


def parse_runs(payload: Any) -> list[datetime]:
    """Reference times, newest first."""
    runs = set()
    for feature in _features(payload):
        stamp = (feature.get("properties") or {}).get("forecast:reference_datetime")
        if isinstance(stamp, str):
            runs.add(datetime.fromisoformat(stamp.replace("Z", "+00:00")))
    return sorted(runs, reverse=True)


def parse_href(payload: Any) -> str | None:
    """The GRIB2 asset of the first matching item, or None when the run has not published it."""
    for feature in _features(payload):
        for asset in (feature.get("assets") or {}).values():
            if isinstance(asset, dict) and asset.get("type") == "application/grib" and asset.get("href"):
                return str(asset["href"])
    return None


def parse_constants_href(payload: Any, model: IconModel) -> str:
    assets = payload.get("assets") if isinstance(payload, dict) else None
    name = f"horizontal_constants_{model.name.lower()}-eps.grib2"
    asset = assets.get(name) if isinstance(assets, dict) else None
    if not isinstance(asset, dict) or not asset.get("href"):
        raise SourceUnavailable(SOURCE, f"{model.stac_collection} lists no {name}")
    return str(asset["href"])


def nearest_cell(lats: Sequence[float], lons: Sequence[float], lat: float, lng: float) -> int:
    """Index of the cell centre nearest (lat, lng), in degrees.

    An equirectangular distance is exact enough at 1 km cells and a few kilometres of search, and
    it vectorises: this runs over ~1.1 million cells.
    """
    import numpy as np

    lat_arr = np.asarray(lats, dtype=np.float64)
    lon_arr = np.asarray(lons, dtype=np.float64)
    dx = (lon_arr - lng) * math.cos(math.radians(lat))
    dy = lat_arr - lat
    return int(np.argmin(dx * dx + dy * dy))


def hourly_precip(accumulated_mm: float | None, previous_mm: float | None) -> float | None:
    """TOT_PREC accumulates from the start of the run; the hour's share is the difference.

    Clamped at zero: decoding noise can make two equal accumulations differ by -1e-6.
    """
    if accumulated_mm is None or previous_mm is None:
        return None
    return max(0.0, accumulated_mm - previous_mm)


def assemble(
    model_run: str,
    hour: int,
    values: dict[str, float | None],
    model_elevation_m: float | None,
    elevation_m: float | None,
) -> PointForecast:
    """Raw values at one cell (SI units, as ICON writes them) to a `PointForecast`."""

    def celsius(name: str) -> float | None:
        kelvin = values.get(name)
        if kelvin is None:
            return None
        celsius = kelvin - KELVIN
        if model_elevation_m is None:
            return celsius
        return lapse_correct(celsius, model_elevation_m, elevation_m)

    u, v = values.get("U_10M"), values.get("V_10M")
    gust = values.get("VMAX_10M")
    return PointForecast(
        model_run=model_run,
        hour=floor_hour(hour),
        temp_c=celsius("T_2M"),
        dewpoint_c=celsius("TD_2M"),
        wind_kmh=wind_speed_kmh(u, v) if u is not None and v is not None else None,
        gust_kmh=gust * MS_TO_KMH if gust is not None else None,
        precip_mm=hourly_precip(values.get("TOT_PREC"), values.get("TOT_PREC_PREV")),
        cape_jkg=values.get("CAPE_ML"),
        cloud_base_m=values.get("CEILING"),
        freezing_level_m=values.get("HZEROCL"),
        snowline_m=values.get("SNOWLMT"),
        model_elevation_m=model_elevation_m,
    )


# --- Decoding -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Grid:
    lats: Any
    lons: Any
    # Model terrain height per cell, when the constants file carries it.
    surface_m: Any | None


class GribDecoder(Protocol):
    def values(self, path: Path) -> Any: ...

    def grid(self, path: Path) -> Grid: ...


# What the fields in `horizontal_constants_*.grib2` are called by plain eccodes (checked against the
# real file: `tlat`/`tlon` in degrees, `h` in metres), and by MeteoSwiss' own COSMO definitions
# should those be installed.
LAT_NAMES = {"tlat", "CLAT"}
LON_NAMES = {"tlon", "CLON"}
SURFACE_NAMES = {"h", "HSURF"}


class EccodesDecoder:
    """The one place `eccodes` is imported."""

    def __init__(self) -> None:
        try:
            import eccodes  # noqa: F401
        except (ImportError, RuntimeError) as exc:
            raise SourceUnavailable(
                SOURCE, f"eccodes is not installed ({exc}): `uv sync --group grib`, or set WEATHER_SOURCE=open-meteo"
            ) from exc

    @staticmethod
    def _messages(path: Path):
        import eccodes

        with path.open("rb") as file:
            while (handle := eccodes.codes_grib_new_from_file(file)) is not None:
                try:
                    yield eccodes.codes_get(handle, "shortName"), eccodes.codes_get_values(handle)
                finally:
                    eccodes.codes_release(handle)

    @lru_cache(maxsize=48)  # noqa: B019 - one decoder per process; bounded, and keyed by file path
    def values(self, path: Path) -> Any:
        import numpy as np

        for _name, values in self._messages(path):
            # float32 halves the memory of the LRU; a gust needs no more than 7 digits.
            return np.asarray(values, dtype=np.float32)
        raise SourceUnavailable(SOURCE, f"{path.name} contains no GRIB message")

    def grid(self, path: Path) -> Grid:
        fields: dict[str, Any] = {}
        for name, values in self._messages(path):
            if name in LAT_NAMES:
                fields["lat"] = values
            elif name in LON_NAMES:
                fields["lon"] = values
            elif name in SURFACE_NAMES:
                fields["surface"] = values
        if "lat" not in fields or "lon" not in fields:
            raise SourceUnavailable(SOURCE, f"{path.name} has no cell-centre coordinates")
        return Grid(fields["lat"], fields["lon"], fields.get("surface"))


# --- The source -----------------------------------------------------------------------------


class IconGribSource:
    def __init__(
        self,
        settings: Settings,
        client: CachedHttpClient,
        *,
        spread: Any | None = None,
        decoder: GribDecoder | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        # Anything with `ensemble_at(point, hour, day) -> dict` — in practice `OpenMeteoIconSource`.
        self.spread = spread
        self._decoder = decoder
        self._grids: dict[str, Grid] = {}
        self._cells: dict[tuple[str, float, float], int] = {}
        self._grid_lock = asyncio.Lock()

    @property
    def decoder(self) -> GribDecoder:
        if self._decoder is None:
            self._decoder = EccodesDecoder()
        return self._decoder

    @property
    def search_url(self) -> str:
        return self.settings.stac_base_url + SEARCH_PATH

    async def runs(self, model: IconModel) -> list[datetime]:
        payload = await self.client.post_json(
            self.search_url,
            key=CacheKey(source=SOURCE, endpoint="runs", params={"model": model.name}),
            ttl_s=self.settings.cache_ttl_run_s,
            json_body=run_search(model),
        )
        runs = parse_runs(payload)
        if not runs:
            raise SourceUnavailable(SOURCE, f"STAC lists no {model.name} runs")
        return runs

    async def newest_run(self, model: IconModel) -> ModelRun:
        return ModelRun(model.name, (await self.runs(model))[0], model.horizon_h)

    async def latest_run(self, day: date | None = None) -> ModelRun:
        _, run = await model_for_day(day or local_today(), self.newest_run)
        return run

    async def forecast_at(self, point: GeoPoint, hour: int, day: date | None = None) -> PointForecast:
        day = day or local_today()
        target = target_time(hour, day)
        model, _ = await model_for_day(day, self.newest_run)
        runs = await self.runs(model)
        self._prune(model, runs)

        reaching = [run for run in runs if ModelRun(model.name, run, model.horizon_h).covers(target)]
        if not reaching:
            raise SourceUnavailable(SOURCE, f"no published {model.name} run reaches {target:%Y-%m-%d %H:%MZ}")

        for run in reaching:
            try:
                forecast = await self._forecast_from(model, run, point, hour, target)
            except Incomplete as exc:
                # The newest run is published step by step; the one before it is complete.
                log.info("icon-grib: %s, falling back to the previous run", exc)
                continue
            if self.spread is not None:
                spread = await self.spread.ensemble_at(point, hour, day)
                if spread:
                    forecast = replace(forecast, **spread)
            return forecast

        raise SourceUnavailable(SOURCE, f"no {model.name} run has published every variable for {target:%H:%MZ}")

    async def _forecast_from(
        self, model: IconModel, run: datetime, point: GeoPoint, hour: int, target: datetime
    ) -> PointForecast:
        label = ModelRun(model.name, run, model.horizon_h).label
        key = CacheKey(
            source=SOURCE, endpoint="point", point=point, model_run=label, params={"target": target.isoformat()}
        )
        cached = self.client.cache.read(key, self.settings.cache_ttl_forecast_s)
        if cached is None:
            cached = await self._extract(model, run, point, target)
            self.client.cache.write(key, cached)
        return assemble(label, hour, cached["values"], cached["modelElevationM"], point.elevation_m)

    async def _extract(self, model: IconModel, run: datetime, point: GeoPoint, target: datetime) -> dict[str, Any]:
        steps = round((target - run).total_seconds() / 3600)
        wanted = [(variable, variable, steps) for variable in GRIB_VARIABLES]
        if steps > 0:
            wanted.append(("TOT_PREC_PREV", "TOT_PREC", steps - 1))

        paths = await asyncio.gather(*(self._message(model, run, variable, step) for _, variable, step in wanted))
        grid, cell = await self._cell(model, point)
        names = [name for name, _, _ in wanted]
        values = await asyncio.to_thread(
            lambda: {name: _finite(self.decoder.values(path)[cell]) for name, path in zip(names, paths, strict=True)}
        )
        surface = _finite(grid.surface_m[cell]) if grid.surface_m is not None else None
        return {"values": values, "modelElevationM": surface}

    async def _message(self, model: IconModel, run: datetime, variable: str, steps: int) -> Path:
        dest = self._run_dir(model, run) / f"{variable.lower()}-{steps}.grib2"
        if dest.is_file():
            return dest
        payload = await self.client.post_json(
            self.search_url,
            key=CacheKey(
                source=SOURCE,
                endpoint="message",
                params={"model": model.name, "run": run.isoformat(), "variable": variable, "steps": steps},
            ),
            # Short: the hrefs are presigned and expire, and an unpublished step may appear soon.
            ttl_s=self.settings.cache_ttl_run_s,
            json_body=message_search(model, run, variable, steps),
        )
        href = parse_href(payload)
        if href is None:
            raise Incomplete(f"{model.name} {run:%Y-%m-%dT%H:%MZ} has not published {variable} at +{steps} h")
        return await self.client.download(href, dest, source=SOURCE)

    async def _cell(self, model: IconModel, point: GeoPoint) -> tuple[Grid, int]:
        grid = await self._grid(model)
        cell_key = (model.name, round(point.lat, COORD_DP), round(point.lng, COORD_DP))
        if cell_key not in self._cells:
            self._cells[cell_key] = await asyncio.to_thread(nearest_cell, grid.lats, grid.lons, point.lat, point.lng)
        return grid, self._cells[cell_key]

    async def _grid(self, model: IconModel) -> Grid:
        async with self._grid_lock:
            if model.name not in self._grids:
                collection = await self.client.get_json(
                    f"{self.settings.stac_base_url}/collections/{model.stac_collection}",
                    key=CacheKey(source=SOURCE, endpoint="collection", params={"model": model.name}),
                    ttl_s=self.settings.cache_ttl_run_s,
                )
                dest = self.settings.grib_dir / model.name.lower() / "horizontal_constants.grib2"
                path = await self.client.download(parse_constants_href(collection, model), dest, source=SOURCE)
                self._grids[model.name] = await asyncio.to_thread(self.decoder.grid, path)
            return self._grids[model.name]

    def _run_dir(self, model: IconModel, run: datetime) -> Path:
        return self.settings.grib_dir / model.name.lower() / f"{run.astimezone(UTC):%Y%m%dT%H%MZ}"

    def _prune(self, model: IconModel, runs: list[datetime]) -> None:
        """Delete the messages of every run but the newest few. The grid constants stay."""
        keep = {self._run_dir(model, run).name for run in runs[:KEEP_RUNS]}
        root = self.settings.grib_dir / model.name.lower()
        if not root.is_dir():
            return
        for entry in root.iterdir():
            if entry.is_dir() and entry.name not in keep:
                shutil.rmtree(entry, ignore_errors=True)
                log.info("icon-grib: pruned superseded run %s", entry.name)


def _finite(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) and number != MISSING else None

