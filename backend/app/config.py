"""Runtime configuration. Read from the environment, or a `.env` file next to the backend."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]

SourceMode = Literal["demo", "live"]
WeatherSourceName = Literal["grib", "open-meteo"]
MINUTE_S = 60

# A forecast goes stale in minutes; a route geometry is good for weeks. Same cache, different TTLs.
HOUR_S = 60 * MINUTE_S
DAY_S = 24 * HOUR_S


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # `demo` serves the hand-authored fixtures; `live` hits the real sources and fails loudly
    # for the ones that are not implemented yet.
    source_mode: SourceMode = "demo"

    # swisstopo: place search and the elevation profile.
    geoadmin_base_url: str = "https://api3.geo.admin.ch"
    # MeteoSwiss OGD: the STAC API that lists ICON model runs.
    stac_base_url: str = "https://data.geo.admin.ch/api/stac/v1"
    # Which live weather source answers. `grib` reads MeteoSwiss' own ICON files and needs eccodes
    # (`uv sync --group grib`); `open-meteo` is the same model over JSON, with nothing to install.
    weather_source: WeatherSourceName = "grib"
    # The fallback weather source: same ICON fields over JSON, no GRIB toolchain. Ensemble spread
    # comes from here for both sources.
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"
    open_meteo_ensemble_url: str = "https://ensemble-api.open-meteo.com/v1"
    # Per-model run metadata (`<model>/static/meta.json`): when the newest run was initialised.
    open_meteo_meta_url: str = "https://api.open-meteo.com/data"
    # Downloaded GRIB messages, deleted once the stop values are extracted from them. The grid
    # constants (cell coordinates, terrain height) stay: they change only when the model does.
    # Defaults to `grib/` under `cache_dir`.
    grib_cache_dir: Path | None = None

    # MeteoSwiss publishes no warnings as open data. The phone app's undocumented API is the only
    # machine-readable feed, so it is opt-in; off, `warnings` stays an honest gap.
    meteoswiss_app_warnings: bool = False
    meteoswiss_app_url: str = "https://app-prod-ws.meteoswiss-app.ch/v1"
    # OSM, for the SAC grades swissTLM3D does not carry.
    overpass_url: str = "https://overpass-api.de/api/interpreter"

    # The routable trail graph, built once by `scripts/import_trails.py`.
    trails_db: Path = BACKEND_DIR / "data" / "trails.sqlite"
    # What that import keeps, as LV95 easting/northing (min_e, min_n, max_e, max_n). The default
    # covers the Bernese Oberland; widen it to route elsewhere, at the cost of import time.
    trails_bbox: tuple[float, float, float, float] = (2_580_000, 1_120_000, 2_680_000, 1_190_000)

    cache_dir: Path = BACKEND_DIR / ".cache"
    # Which run is newest: checked often, because a new run should replace cached forecasts soon.
    cache_ttl_run_s: int = 10 * MINUTE_S
    cache_ttl_forecast_s: int = 30 * MINUTE_S
    cache_ttl_warnings_s: int = 10 * MINUTE_S
    cache_ttl_route_s: int = 30 * DAY_S
    cache_ttl_search_s: int = DAY_S

    http_timeout_s: float = 20.0
    # Total attempts, not retries after the first: 1 disables retrying.
    http_attempts: int = 3
    http_backoff_s: float = 0.5

    # None of the sources need a key today. Kept so adding one is configuration, not code.
    open_meteo_api_key: str | None = None

    # Hazard narration: a language model rephrases the computed hazards, under the copy rules. Any
    # OpenAI-compatible chat completions endpoint (vLLM, NVIDIA NIM, …) works. Off, or without a
    # base URL, the app shows its templated copy and nothing else changes.
    narration_enabled: bool = False
    # Up to and including `/v1`, e.g. `https://…/v1`; `/chat/completions` is appended.
    narration_base_url: str | None = None
    narration_api_key: str | None = None
    narration_model: str = "nvidia/nemotron-3-nano-30b-a3b"
    # Reasoning models think before they answer. Phrasing needs none of it, and it costs latency.
    narration_thinking: bool = False
    narration_timeout_s: float = 60.0
    cache_ttl_narration_s: int = 30 * MINUTE_S

    # Serve the MCP server over streamable HTTP at `/mcp`, next to the REST API.
    mcp_http: bool = True

    @property
    def narration_configured(self) -> bool:
        return self.narration_enabled and bool(self.narration_base_url)

    @property
    def grib_dir(self) -> Path:
        return self.grib_cache_dir or self.cache_dir / "grib"


@lru_cache
def get_settings() -> Settings:
    """Cached so the app reads the environment once. Tests call `get_settings.cache_clear()`."""
    return Settings()
