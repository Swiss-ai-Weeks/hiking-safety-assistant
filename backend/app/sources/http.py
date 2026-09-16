"""Shared HTTP plumbing for the live sources: retry with backoff, and a disk cache.

Forecast pulls are slow and rate-limited, so the cache is keyed by what actually identifies a
forecast value — model run, coordinate and hour — rather than by URL. The same point at the same
hour from the same run is fetched once.
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from ..config import Settings
from ..domain import GeoPoint
from .base import SourceUnavailable

log = logging.getLogger(__name__)

# ~11 m. Coordinates are rounded before they enter a cache key so that floating-point noise in
# an interpolated route point cannot miss an otherwise identical entry.
COORD_DP = 4

USER_AGENT = "hiking-safety-assistant/0.1 (+https://github.com/Swiss-ai-Weeks/hiking-safety-assistant)"


class _Retryable(Exception):
    """Transport failure or 5xx: worth trying again. A 4xx never is."""


@dataclass(slots=True)
class CacheKey:
    """What identifies a cached value. Stored alongside it, so a cache dir is inspectable."""

    source: str
    endpoint: str
    point: GeoPoint | None = None
    model_run: str | None = None
    hour: int | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        point = None
        if self.point is not None:
            point = [round(self.point.lat, COORD_DP), round(self.point.lng, COORD_DP)]
            if self.point.elevation_m is not None:
                point.append(round(self.point.elevation_m))
        return {
            "source": self.source,
            "endpoint": self.endpoint,
            "point": point,
            "modelRun": self.model_run,
            "hour": self.hour,
            "params": {k: self.params[k] for k in sorted(self.params)},
        }

    def digest(self) -> str:
        blob = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()[:32]


class DiskCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, key: CacheKey) -> Path:
        return self.root / key.source / f"{key.digest()}.json"

    def read(self, key: CacheKey, ttl_s: float) -> Any | None:
        path = self.path_for(key)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Missing, unreadable or half-written: a miss, never an error.
            return None
        if time.time() - entry.get("storedAt", 0) > ttl_s:
            return None
        return entry.get("body")

    def write(self, key: CacheKey, body: Any) -> None:
        path = self.path_for(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            entry = {"key": key.as_dict(), "storedAt": time.time(), "body": body}
            # Write-then-rename: a crash mid-write cannot leave a truncated entry behind.
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            log.warning("could not cache %s", path, exc_info=True)


class CachedHttpClient:
    """`httpx.AsyncClient` with retry and the disk cache in front of it."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.cache = DiskCache(settings.cache_dir)
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _connection(self) -> httpx.AsyncClient:
        """The client, created on first use and rebuilt if the event loop underneath it changed.

        `get_sources` is cached for the process, so one `CachedHttpClient` outlives any single
        loop. An `AsyncClient` holds connections bound to the loop that opened them, and reusing
        one across loops fails with "Event loop is closed" — which is exactly what a `TestClient`
        does, a request per loop. Under uvicorn there is one loop and this builds one client.
        """
        loop = asyncio.get_running_loop()
        if self._client is None or self._loop is not loop:
            self._client = httpx.AsyncClient(
                timeout=self.settings.http_timeout_s,
                transport=self._transport,
                # Overpass answers 406 to a request without a User-Agent, and it is good manners
                # to say who is calling a free public API in any case.
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            )
            self._loop = loop
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "CachedHttpClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def get_json(self, url: str, *, key: CacheKey, ttl_s: float, params: dict[str, Any] | None = None) -> Any:
        cached = self.cache.read(key, ttl_s)
        if cached is not None:
            return cached
        body = await self._fetch(url, key.source, params)
        self.cache.write(key, body)
        return body

    async def post_json(self, url: str, *, key: CacheKey, ttl_s: float, data: dict[str, Any]) -> Any:
        """Same cache and retry as `get_json`, for the requests too large to be a URL.

        A routed polyline has hundreds of vertices; as a query parameter it overruns what
        swisstopo's profile endpoint accepts. The cache key still describes the *request*, not
        the method, so a cached profile is a cached profile either way.
        """
        cached = self.cache.read(key, ttl_s)
        if cached is not None:
            return cached
        body = await self._fetch(url, key.source, None, form=data)
        self.cache.write(key, body)
        return body

    async def _fetch(
        self, url: str, source: str, params: dict[str, Any] | None, form: dict[str, Any] | None = None
    ) -> Any:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self.settings.http_attempts),
            wait=wait_exponential_jitter(
                initial=self.settings.http_backoff_s,
                jitter=self.settings.http_backoff_s,
            ),
            retry=retry_if_exception_type(_Retryable),
            reraise=True,
        )
        try:
            return await retrying(self._once, url, source, params, form)
        except _Retryable as exc:
            attempts = self.settings.http_attempts
            raise SourceUnavailable(source, f"{url} failed after {attempts} attempts: {exc}") from exc

    async def _once(self, url: str, source: str, params: dict[str, Any] | None, form: dict[str, Any] | None) -> Any:
        try:
            connection = self._connection()
            if form is None:
                response = await connection.get(url, params=params)
            else:
                response = await connection.post(url, data=form)
        except httpx.TransportError as exc:
            raise _Retryable(str(exc)) from exc
        if response.status_code >= 500:
            raise _Retryable(f"HTTP {response.status_code}")
        if response.status_code >= 400:
            # The request itself is wrong. Retrying would only repeat it.
            raise SourceUnavailable(source, f"{url} returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise SourceUnavailable(source, f"{url} returned a non-JSON body") from exc
