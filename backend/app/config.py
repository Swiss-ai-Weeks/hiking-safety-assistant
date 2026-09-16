"""Runtime configuration. Read from the environment, or a `.env` file next to the backend."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]

SourceMode = Literal["demo", "live"]

# A forecast goes stale in minutes; a route geometry is good for weeks. Same cache, different TTLs.
HOUR_S = 60 * 60
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
    # The fallback weather source: same ICON fields over JSON, no GRIB toolchain.
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"

    cache_dir: Path = BACKEND_DIR / ".cache"
    cache_ttl_forecast_s: int = 30 * 60
    cache_ttl_route_s: int = 30 * DAY_S
    cache_ttl_search_s: int = DAY_S

    http_timeout_s: float = 20.0
    # Total attempts, not retries after the first: 1 disables retrying.
    http_attempts: int = 3
    http_backoff_s: float = 0.5

    # None of the sources need a key today. Kept so adding one is configuration, not code.
    open_meteo_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Cached so the app reads the environment once. Tests call `get_settings.cache_clear()`."""
    return Settings()
