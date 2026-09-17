"""Hit every real source once from this machine and print what answers.

    uv run --directory backend python -m scripts.smoke_live [--app https://…] [--skip-model]

The test suite replays recorded responses and never touches the network, so it cannot tell whether
*this* VM reaches swisstopo, MeteoSwiss, Open-Meteo, Overpass or the language model. This does, through
the app's own source classes and an empty cache, so a pass means the code path the service uses works.
The weather lines also say how old each model's newest run is and whether it reaches tomorrow's hike:
publication running late is what turned a whole day into "not evaluated" once.

Exit status is non-zero when a required check fails. Optional checks (app warnings, the model, the
app itself when not asked for) are reported but never fail the run.
"""

import argparse
import asyncio
import csv
import io
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.domain import GeoPoint
from app.sources.geoadmin import GeoAdminRouteSource
from app.sources.http import USER_AGENT, CachedHttpClient
from app.sources.icon_grib import IconGribSource
from app.sources.names import SwissNamesSource
from app.sources.openmeteo import OpenMeteoIconSource
from app.sources.osm import OverpassGradeSource
from app.sources.swissalti import SwissAltiElevationSource
from app.sources.warnings_app import AppWarningSource
from app.sources.weather_common import DAY_LAST_HOUR, MODELS, local_today, target_time

OESCHINENSEE = GeoPoint(46.49836, 7.72667, 1578)
HOHTURLI = GeoPoint(46.4888, 7.7717, 2778)
SHOWCASE_ROUTE = "oeschinensee-bluemlisalphuette"
SMN_STATION = "abo"  # Adelboden, the SMN station nearest the showcase route
TILE = "https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-farbe/default/current/3857/13/4271/2898.jpeg"


@dataclass
class Result:
    name: str
    ok: bool
    ms: float
    detail: str
    required: bool


Check = Callable[[], Awaitable[str]]


async def run(name: str, check: Check, required: bool = True) -> Result:
    started = time.monotonic()
    try:
        detail = await check()
        ok = True
    except Exception as exc:  # the point is to report, whatever broke
        detail = f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"
        ok = False
    return Result(name, ok, (time.monotonic() - started) * 1000, detail, required)


def age(reference: datetime) -> str:
    hours = (datetime.now(UTC) - reference).total_seconds() / 3600
    return f"{hours:.0f} h old"


def source_checks(settings: Settings, client: CachedHttpClient) -> list[tuple[str, Check, bool]]:
    open_meteo = OpenMeteoIconSource(settings, client)
    stac = IconGribSource(settings, client)
    tomorrow = local_today() + timedelta(days=1)
    tomorrow_end = target_time(DAY_LAST_HOUR, tomorrow)

    async def search() -> str:
        hits = await GeoAdminRouteSource(settings, client).search("Kandersteg")
        assert hits, "no hits"
        return f"{len(hits)} places, first {hits[0].name!r}"

    async def profile() -> str:
        result = await SwissAltiElevationSource(settings, client).profile([OESCHINENSEE, HOHTURLI])
        heights = [p.elevation_m for p in result.points if p.elevation_m is not None]
        assert heights, "no heights"
        return f"{len(result.points)} points, {min(heights):.0f}–{max(heights):.0f} m"

    async def names() -> str:
        places = await SwissNamesSource(settings, client).along(
            [(OESCHINENSEE.lat, OESCHINENSEE.lng), (HOHTURLI.lat, HOHTURLI.lng)]
        )
        return f"{len(places)} named places along the line"

    async def overpass() -> str:
        index = await OverpassGradeSource(settings, client).grades_for((46.48, 7.72, 46.50, 7.78))
        return f"{len(index.ways)} ways"

    async def tile() -> str:
        async with httpx.AsyncClient(timeout=settings.http_timeout_s, headers={"User-Agent": USER_AGENT}) as http:
            response = await http.get(TILE)
        response.raise_for_status()
        return f"{response.headers.get('content-type')} {len(response.content) // 1024} KB"

    def open_meteo_run(model) -> Check:
        async def check() -> str:
            run = await open_meteo.run_of(model)
            end = run.reference_time + timedelta(hours=run.horizon_h)
            reaches = "reaches" if end >= tomorrow_end else "DOES NOT reach"
            return f"{run.label}, {age(run.reference_time)}, ends {end:%a %H:%MZ}, {reaches} tomorrow's hike"

        return check

    def stac_run(model) -> Check:
        async def check() -> str:
            runs = await stac.runs(model)
            end = runs[0] + timedelta(hours=model.horizon_h)
            return f"newest {runs[0]:%Y-%m-%dT%H:%MZ}, {age(runs[0])}, ends {end:%a %H:%MZ}, {len(runs)} listed"

        return check

    async def day_model() -> str:
        run = await open_meteo.latest_run(tomorrow)
        return f"tomorrow ({tomorrow}) is served by {run.label}"

    async def forecast() -> str:
        point = await open_meteo.forecast_at(HOHTURLI, 12 * 60, tomorrow)
        spread = "with" if point.has_spread else "WITHOUT"
        return f"Hohtürli 12:00 tomorrow: {point.temp_c:.1f} °C, gusts {point.gust_kmh:.0f} km/h, {spread} spread"

    async def smn() -> str:
        async with httpx.AsyncClient(timeout=settings.http_timeout_s, headers={"User-Agent": USER_AGENT}) as http:
            item = (
                await http.get(f"{settings.stac_base_url}/collections/ch.meteoschweiz.ogd-smn/items/{SMN_STATION}")
            ).json()
            href = item["assets"][f"ogd-smn_{SMN_STATION}_t_now.csv"]["href"]
            response = await http.get(href)
        response.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(response.text), delimiter=";"))
        assert rows, "empty CSV"
        stamp = datetime.strptime(rows[-1]["reference_timestamp"], "%d.%m.%Y %H:%M").replace(tzinfo=UTC)
        temp = rows[-1].get("tre200s0", "?")
        return f"station {SMN_STATION.upper()} last observation {stamp:%H:%MZ} ({age(stamp)}), {temp} °C"

    async def app_warnings() -> str:
        if not settings.meteoswiss_app_warnings:
            return "off (METEOSWISS_APP_WARNINGS=false): warnings are a reported gap"
        warnings = await AppWarningSource(settings, client).warnings_for([OESCHINENSEE])
        return f"{len(warnings)} warnings at Oeschinensee"

    checks: list[tuple[str, Check, bool]] = [
        ("swisstopo search", search, True),
        ("swissALTI3D profile", profile, True),
        ("swissNAMES3D identify", names, True),
        ("swisstopo WMTS tile", tile, True),
        ("OSM Overpass", overpass, False),
    ]
    for model in MODELS:
        checks.append((f"Open-Meteo {model.name} run", open_meteo_run(model), True))
    checks.append(("Open-Meteo day model", day_model, True))
    checks.append(("Open-Meteo forecast+ensemble", forecast, True))
    for model in MODELS:
        checks.append((f"MeteoSwiss STAC {model.name}", stac_run(model), False))
    checks.append(("MeteoSwiss SMN station", smn, False))
    checks.append(("MeteoSwiss app warnings", app_warnings, False))
    return checks


def model_checks(settings: Settings) -> list[tuple[str, Check, bool]]:
    headers = {"User-Agent": USER_AGENT}
    if settings.narration_api_key:
        headers["Authorization"] = f"Bearer {settings.narration_api_key}"
    base = (settings.narration_base_url or "").rstrip("/")

    async def models() -> str:
        if not settings.narration_configured:
            return "narration off (NARRATION_ENABLED / NARRATION_BASE_URL unset)"
        async with httpx.AsyncClient(timeout=15, headers=headers) as http:
            response = await http.get(f"{base}/models")
        response.raise_for_status()
        ids = [model["id"] for model in response.json().get("data", [])]
        assert settings.narration_model in ids, f"{settings.narration_model!r} not in {ids}"
        return f"{base} serves {settings.narration_model}"

    async def completion() -> str:
        if not settings.narration_configured:
            return "skipped"
        body = {
            "model": settings.narration_model,
            "messages": [{"role": "user", "content": "/no_think Reply with the single word: ready"}],
            "max_tokens": 10,
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        async with httpx.AsyncClient(timeout=settings.narration_timeout_s, headers=headers) as http:
            response = await http.post(f"{base}/chat/completions", json=body)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return f"answered {content.strip()[:40]!r}"

    return [("Nemotron models", models, False), ("Nemotron completion", completion, False)]


def app_checks(url: str) -> list[tuple[str, Check, bool]]:
    base = url.rstrip("/")
    tomorrow = (local_today() + timedelta(days=1)).isoformat()

    async def get(path: str, **params: Any) -> Any:
        async with httpx.AsyncClient(timeout=120) as http:
            response = await http.get(base + path, params=params)
        response.raise_for_status()
        return response.json()

    async def health() -> str:
        body = await get("/api/health")
        return f"mode {body['mode']}"

    async def assessment() -> str:
        body = await get(f"/api/routes/{SHOWCASE_ROUTE}/assessment", date=tomorrow)
        forecast = body["forecast"]
        kinds = sorted({hazard["kind"] for hazard in body["hazards"]})
        unevaluated = sum(len(item["legIds"]) for item in body.get("notEvaluated", []))
        return (
            f"{body['outcome']} from {forecast['model']}, stale={body['stale']}, "
            f"hazards {kinds or 'none'}, {unevaluated} legs not evaluated"
        )

    async def narration() -> str:
        body = await get(f"/api/routes/{SHOWCASE_ROUTE}/narration", date=tomorrow, lang="en")
        phrased = sum(1 for hazard in body["hazards"] if hazard.get("body"))
        return f"enabled={body['enabled']}, {phrased}/{len(body['hazards'])} bodies phrased"

    async def ask() -> str:
        async with httpx.AsyncClient(timeout=120) as http:
            response = await http.post(
                f"{base}/api/routes/{SHOWCASE_ROUTE}/ask",
                params={"date": tomorrow, "lang": "en"},
                json={"question": "Which part of the route is the most exposed?"},
            )
        if response.status_code in (404, 405):
            return "no /ask endpoint on this build"
        response.raise_for_status()
        body = response.json()
        return f"{body['reason']}: {(body.get('text') or '')[:80]!r}"

    async def mcp() -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "smoke-live", "version": "1"},
            },
        }
        headers = {"Accept": "application/json, text/event-stream"}
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.post(f"{base}/mcp", json=payload, headers=headers)
        response.raise_for_status()
        assert "serverInfo" in response.text, response.text[:200]
        return "initialize answered"

    return [
        ("app health", health, True),
        ("app assessment (tomorrow)", assessment, True),
        ("app narration", narration, False),
        ("app ask", ask, False),
        ("app MCP", mcp, False),
    ]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", help="Also check a running app at this base URL")
    parser.add_argument("--skip-sources", action="store_true", help="Only check the model and the app")
    parser.add_argument("--skip-model", action="store_true", help="Do not call the language model")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as cache:
        # An empty cache and a single attempt: what answers now, not what answered an hour ago.
        settings = get_settings().model_copy(update={"cache_dir": Path(cache), "http_attempts": 1})
        client = CachedHttpClient(settings)
        checks: list[tuple[str, Check, bool]] = []
        if not args.skip_sources:
            checks += source_checks(settings, client)
        if not args.skip_model:
            checks += model_checks(settings)
        if args.app:
            checks += app_checks(args.app)

        results = [await run(name, check, required) for name, check, required in checks]

    width = max(len(result.name) for result in results)
    for result in results:
        mark = "OK  " if result.ok else ("FAIL" if result.required else "warn")
        print(f"{mark}  {result.name:<{width}}  {result.ms:7.0f} ms  {result.detail}")
    failed = [result for result in results if result.required and not result.ok]
    passed = sum(result.ok for result in results)
    summary = f"\n{passed}/{len(results)} checks passed"
    print(summary + (f", {len(failed)} required failed" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
