# Making it work for real

The frontend is complete and the backend is a typed mock server. Every value the
app shows today is hand-authored: `backend/app/mock_data.py` types in the severity
of each hazard at each stop, the leg times are written by hand, and the hazard
prose in `frontend/src/i18n/en.ts` has the numbers baked into the sentence
("Gusts of 50-60 km/h", "Freezing level 2 900 m"). Nothing is computed from data.

This plan replaces the mock with swisstopo route data, MeteoSwiss forecasts and a
hazard engine, then adds the MCP and RAG layers the challenge brief asks for.

## Decisions

| Question | Choice |
|---|---|
| Routing source | swissTLM3D Wanderwege (the official network the UI already claims) |
| Weather source | MeteoSwiss ICON GRIB2 first, Open-Meteo as a same-interface fallback |
| AI layer | Full: MCP server, RAG, guard-railed LLM narration |

## Constraint: no egress in some dev containers

`api3.geo.admin.ch` and `data.geo.admin.ch` are blocked by *some* dev environments'
egress policy (403 on CONNECT) — but not by all of them; both are reachable from a
normal workstation. Source code is written against recorded fixtures and unit-tested
offline either way, because a test suite that needs the network is a test suite that
fails on stage. `pytest --record` refreshes the fixtures wherever egress does work;
`scripts/smoke-live.sh` (Phase 6) is what confirms the VM itself can reach a source.

## Phase 0 - Seams and offline testability (~3 h) - done

1. `backend/app/config.py` - pydantic-settings: `SOURCE_MODE=demo|live`, base URLs,
   cache directory and TTLs, optional API keys.
2. `backend/app/sources/base.py` - `RouteSource`, `ElevationSource`, `WeatherSource`,
   `WarningSource` protocols. They return domain objects, never raw payloads.
3. `backend/app/sources/demo.py` - today's `mock_data.py` behind those protocols, so
   the four demo scenarios and `backend/tests/test_api.py` keep working.
4. HTTP layer: `httpx` + `tenacity` (retry/backoff) + a disk cache keyed by
   *model run + point + hour*. Forecast pulls are slow and rate-limited.
5. Fixtures: record real responses on the VM into `backend/tests/fixtures/`, replay
   offline. Every source gets a `test_*_parses_fixture`.
6. Generate `frontend/src/domain/types.ts` from the OpenAPI schema
   (`openapi-typescript`) instead of maintaining it by hand next to `models.py`.

Exit: `SOURCE_MODE=demo` behaves exactly as now, `live` is selectable and fails loudly.

Landed in `bddad45`. The exit criterion was checked literally rather than assumed:
every endpoint was captured before the change and diffed after, and only
`/api/health` differs — by the `mode` key it now reports, so you can tell from
outside which sources a running service is using.

The type contract turned out to be worth more than expected. Renaming a field in
`models.py` now fails twice, both offline: `pytest` on the committed
`backend/openapi.json` snapshot, and `tsc -b` at the matching assertion in
`frontend/src/api/contract.ts`. Four deviations from the plan above:

- `types.ts` stays hand-written rather than generated, because its comments carry
  rules the UI depends on (`Severity` has no "green"); the generated `schema.d.ts`
  is what it is checked against. The assertions strip `null` at every depth, since
  pydantic describes an optional field as `anyOf: [T, null]` while
  `response_model_exclude_none=True` means null is never actually sent.
- A fifth protocol, `Assessor`, beyond the four listed. `get_assessment` is what
  `api.py` actually calls, and Phase 3's hazard engine replaces exactly that —
  without the seam, Phase 3 would have to edit `api.py`.
- `live` fails **per source**, not at startup: unimplemented sources raise
  `SourceUnavailable` when called (mapped to a 503 naming the phase that owns them),
  and startup logs a warning listing them. Failing at startup would have blocked
  Phases 1 and 2 from landing independently.
- Phase 1's place search (`GeoAdminRouteSource.search`) is implemented already, as
  the thing the fixture harness is proven against. It is the only live source that
  answers today. No endpoint exposes it yet, so the API surface is unchanged.

Internal domain objects live in `backend/app/domain.py` as plain dataclasses, not
pydantic models, so they cannot reach a response and leak into the generated schema;
a test asserts that.

## Phase 1 - Real routes (~14 h)

swissTLM3D Wanderwege (`ch.swisstopo.swisstlm3d-wanderwege`) downloaded once into
GeoPackage/SQLite, loaded into a `networkx` graph, routed with Dijkstra.

1. `GET /api/routes/search?q=` - place-name search via swisstopo `SearchServer`
   (`type=locations`), for a real route picker. The source side of this landed in
   Phase 0 (`GeoAdminRouteSource.search`); what is left is the endpoint.
2. `POST /api/routes` (from, to, via) - route the graph, return geometry.
3. Elevation: `api3.geo.admin.ch/rest/services/profile.json` (swissALTI3D) over the
   geometry, for ascent and descent per segment.
4. Timing model replacing hand-written `legMinutes`: SAC / DIN 33466
   (`max(horizontal, vertical) + min(...)/2`), penalised by difficulty. This is what
   makes `computeArrivals` and the pace factors in `frontend/src/domain/timing.ts` mean
   something.
5. Stop selection (`backend/app/routing/stops.py`) - a real route has thousands of
   points and the timeline wants five to seven: start, huts, passes, junctions, the
   crux (steepest exposed segment), turnaround, return leg.
6. Legs are runs of constant grade between stops; `cruxStopId` and `bailoutName` are
   derived rather than typed.

TLM3D carries no SAC scale, so grade and the `cables` flag are cross-referenced
against OSM tags (`sac_scale`, `assisted_trail`, `trail_visibility`) matched onto the
TLM3D geometry. Where no match exists the leg is graded conservatively and reported
as a gap rather than guessed.

## Phase 2 - Real weather (~8 h)

MeteoSwiss OGD via the STAC API on `data.geo.admin.ch/api/stac/v1`:

- `ch.meteoschweiz.ogd-forecasting-icon-ch1` - ~1 km, hourly, short range: day-of.
- `ch.meteoschweiz.ogd-forecasting-icon-ch2` - coarser, ~5 days: planning ahead.
- `ch.meteoschweiz.ogd-smn` - station observations (CSV): nowcast and sanity check.
- The official warnings layer - fills the `warnings` gap currently hardcoded.

Variables: 10 m wind and gusts, precipitation, 2 m temperature, dewpoint, cloud base,
freezing level, CAPE / thunderstorm probability.

These are GRIB2 and need `eccodes` plus `cfgrib`/`xarray`. Pull only the required
variables and interpolate at the handful of stop coordinates - never materialise
grids. The ensemble gives uncertainty for free, which is what "partially assessed"
should mean.

`WeatherSource` is implemented twice: `IconGribSource` (official) and
`OpenMeteoIconSource` (same ICON fields over JSON, no GRIB toolchain), switched by one
env var, so a stalled GRIB toolchain cannot sink demo day.

Output: `forecast_at(lat, lng, elevation_m, hour) -> PointForecast`, plus the real
`issuedAt` behind the stale banner.

## Phase 3 - The hazard engine (~6 h)

`backend/app/hazards/` maps (terrain x forecast x arrival hour) to severity per stop:
gusts, showers and wet rock, thunderstorms, cold and wind chill, freezing level and
snowline, visibility against cloud base, and daylight against the return ETA.

Three decisions shape the API:

- **Evaluation stays client-side.** `frontend/src/domain/assessment.ts` already resolves
  severity at arrival time, which keeps moving the start time instant and offline.
  Generalise `HazardDef.stops` from `{stopId: Severity}` to
  `{stopId: [{from, to, severity}]}` (hourly intervals); `hazardSeverityAt` becomes a
  lookup.
- **`outcome` is derived, not requested.** `assessed` when every stop is covered,
  `partial` when legs fall outside grid or altitude coverage or the ensemble spread is
  too wide (this populates `notEvaluated`), `not_assessable` when the fetch fails. The
  `?scenario=` parameter survives under `SOURCE_MODE=demo` so the four states stay
  demoable.
- **Alternatives are computed.** Re-run the engine at start-30/-60/-90 min and emit
  `startEarlier` only when it actually clears the hazard; `altRoute` re-routes around
  the flagged segment using Phase 1.

Also: real `provenance` strings (rule id, version, model run) and a
`/api/forecast/retry` that actually re-checks.

## Phase 4 - Frontend generalisation (~5 h)

1. Data-driven hazard copy: a `facts` object per hazard (`gustKmh`, `freezingLevelM`,
   `tempC`) and i18n strings with placeholders, EN and FR for every hazard kind.
   `copy-rules.test.ts` enforces placeholder parity and bans verdict words.
2. A route picker screen searching `/api/routes/search`, replacing the hardcoded route
   card and the "demo data covers the Oeschinensee route only" note.
3. Real recent routes, or drop the endpoint.
4. Map: `LABEL_POSITION` in `RouteMapScreen.tsx` is keyed on demo waypoint ids -
   replace with automatic label placement. Prefer swisstopo raster tiles
   (`wmts.geo.admin.ch`, `pixelkarte-farbe`) over OSM tiles for alpine terrain.
5. Field mode becomes real: `navigator.geolocation.watchPosition` snapped to the
   polyline gives elapsed, remaining and next ascent, and recomputes ETA and turnaround
   live. Deletes `route.field`.

## Phase 5 - The AI layer (~6 h)

1. **MCP server** (`backend/app/mcp_server.py`, FastMCP) exposing `search_route`,
   `get_route`, `forecast_at`, `assess_route`, so any agent can drive the same engine.
2. **RAG** over a small curated corpus (SAC hiking-scale definitions, MeteoSwiss warning
   semantics, SLF and alpine safety guidance) used to ground the explanations and cite a
   source in `provenance`.
3. **LLM narration** turning computed hazards into prose under strict guard rails:
   numbers come from `facts` and are never generated, verdict words stay banned, and the
   copy-rules test is extended to cover generated text. The rules engine decides; the
   model only phrases. Behind a flag, so a missing key degrades to templated copy.

## Phase 6 - Ops and verification (~3 h)

- An error taxonomy mapping source failures onto `not_assessable` / `partial` / specific
  gaps, so degradation is honest rather than silent.
- Warm the cache for the showcase routes at startup: insurance against a slow GRIB pull
  on stage.
- `scripts/smoke-live.sh` - hits every real source once from the VM and prints what is
  reachable. The only place the blocked-egress gap closes.
- New env vars in `deploy/hiking-safety-assistant.service`; document the eccodes system
  dependency.
- Playwright end-to-end tests over the built app for the four outcome states.

## Order

Phase 0 first and alone. Phases 1 and 2 then run in parallel on separate files. Phase 3
needs both. Phase 4 can start once Phase 3's API shape is agreed. Phase 5 needs 1-3 but
nothing from 4. Roughly 45 h sequential, roughly 22 h with three people.

If time runs short, Phases 0-3 alone are a working product: one searched route, a real
forecast, real computed hazards.

## Risks

1. The GRIB toolchain (eccodes install, file sizes). Mitigated by the dual `WeatherSource`.
2. Building a routable graph from swissTLM3D is the largest single unknown, and grade data
   has to come from a second source.
3. Stop selection quality: the timeline is the heart of the UI, and auto-picked stops can
   look arbitrary where hand-picked ones looked inevitable. Budget iteration.
