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

## Phase 1 - Real routes (~14 h) - done

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

### What landed

`POST /api/routes` and `GET /api/routes/search` are live; the computed Oeschinensee route
comes out at 10.2 km and 1 200 m against the hand-authored 11.2 km and 1 220 m, picks
Hohtürli as its crux and Berghaus Oberbärgli as its bail-out — the same choices
`mock_data.py` made by hand, arrived at from the data. Six deviations from the plan above,
all of them things the sources turned out to say:

- **TLM3D does carry a hiking classification.** The plan assumed it did not, and swisstopo's
  published API layer agrees — `hikingtype` is null at every point probed. The GeoPackage is
  a different story: `wanderwege` is populated on all 409,276 rows as `Wanderweg` /
  `Bergwanderweg` / `Alpinwanderweg`, the official signposting scheme. So OSM is no longer the
  grade source but a *refinement*: TLM3D sets a floor that is complete and authoritative, OSM
  can raise it within a class, and no leg is ever ungraded. OSM's `sac_scale` covers about a
  third of the ways around the demo route, which would have left the rest guessed.
- **`assisted_trail` is not the cables tag.** It has zero coverage in the Bernese Oberland.
  `safety_rope`, `ladder` and `via_ferrata_scale` are what is actually used.
- **A grade needs corroboration.** Matching one point per segment let a 13 m connector read T5
  off a stray via ferrata crossing it. A promotion now has to be carried by at least two
  samples, a quarter of them, and spread over at least 100 m of trail.
- **Snapping is to the nearest line, not the nearest node.** TLM3D lines run up to 4.7 km, so
  nodes are far apart; snapping to them put the Oeschinensee start 145 m above the lake.
- **The crux is a sliding 500 m window,** not the steepest segment — per segment, the winner
  was a 24 m connector rising 11 m.
- **swisstopo's services reject WGS84.** `profile.json` answers HTTP 400 ("valid number for the
  spatial reference system model: 21781, 2056") and `MapServer/identify` silently returns an
  empty result set. Everything goes out in LV95; `app/projection.py` holds the transformers.

Two things the plan did not ask for but Phase 1 needed. The elevation profile and place-name
lookups are POSTs and Overpass rejects a request with no `User-Agent`, so `CachedHttpClient`
grew `post_json` and a `User-Agent`; and its `AsyncClient` is now built lazily per event loop,
because `get_sources` is cached for the process while a `TestClient` uses a loop per request.

Layering is now checked by the import graph rather than by intention: `routing/` imports nothing
from `sources/`. Getting there moved `SourceUnavailable` to `app/errors.py`, `NamedPlace` to
`domain.py` and the OSM geometry matching to `routing/grades.py`, leaving `sources/osm.py`
responsible only for fetching and parsing.

Frontend work was held to what a computed route needs in order to render: the new fields and
their contract assertions, automatic map labels replacing `LABEL_POSITION`, legs drawn along the
real geometry, and `?routeId=`. The picker screen stays in Phase 4.

Tests run offline. `tests/fixtures/trails_oeschinensee.sqlite` is the real import clipped to 90
edges (256 KB), so the graph, timing, stop selection and assembly are all exercised against real
swisstopo geometry with no network; the three live sources replay recorded responses.

## Phase 2 - Real weather (~8 h) - done

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

### What landed

`WeatherSource` is live twice over, as planned: `IconGribSource` (`sources/icon_grib.py`) and
`OpenMeteoIconSource` (`sources/openmeteo.py`), switched by `WEATHER_SOURCE=grib|open-meteo`. The
protocol gained `day` and `latest_run() -> ModelRun`, whose `reference_time` is the real `issuedAt`.
Both were run against the live services for the same stops. At 23:00 from the ICON-CH1 15Z run they
agree on the run, to within a degree on temperature and to within 60 m on freezing level at
Oeschinensee and Hohtürli. No wire model changed: `openapi.json` and the frontend are untouched,
because Phase 3 is what turns a `PointForecast` into hazards. What the sources turned out to say:

- **MeteoSwiss publishes no warnings as open data.** They are absent from the OGD STAC catalogue,
  and the geo.admin layers carry only FOEN's forest-fire, drought and flood maps. The only
  machine-readable feed is the undocumented API behind the MeteoSwiss app (`plzDetail`, keyed by
  postcode). `AppWarningSource` uses it behind `METEOSWISS_APP_WARNINGS` (off by default). It maps
  route points to postcodes with swisstopo's locality directory and marks every warning
  `official=False`. Off or failing, it raises `SourceUnavailable`, so `warnings` stays a reported gap
  and never reads as an empty all-clear. Only `warnType` 10 (forest fire) is confirmed against a live
  response; the rest of the code table is inferred.
- **One GRIB file per variable per forecast hour.** The control run is 2.3 MB per file and the
  10-member ensemble 23 MB, on the native unstructured grid (1 147 980 cells). The ensemble in GRIB
  would be ~2 GB per run for a day hike, so the GRIB source reads the control run only. Spread
  (p10/p90 of gusts and precipitation, and `thunder_probability` as the share of members with
  mixed-layer CAPE ≥ 500 J/kg) comes from Open-Meteo's ensemble API for both sources. The caveat:
  the two pick grid cells independently, so at a ridge stop the GRIB control value can sit outside
  the Open-Meteo spread (at Hohtürli: control gust 45 km/h against a 32–36 km/h spread). Phase 3
  should read the spread as uncertainty, not as bounds on the value.
- **"Never materialise grids" became "never serve one".** The STAC search caps at 100 items, does
  not page, and takes one variable per query. A downloaded message covers every stop at that hour,
  so messages stay on disk while their run is current and superseded runs are pruned (two are kept).
  Only per-point values are cached under run + point + hour. A cold first forecast takes about a
  minute (34 MB of grid constants plus 11 messages); later stops and hours for the same run take
  milliseconds. Phase 6's cache warm-up matters for the GRIB source.
- **The newest run is published step by step.** If a step is missing from it, the source falls
  back to the previous run rather than failing.
- **Cell centres are `tlat`/`tlon` in degrees, terrain height is `h`**, and ICON writes no bitmap:
  an undefined value (a snowfall limit when nothing falls) comes back as `9999`, which is now `None`.
  The nearest cell to Hohtürli has terrain at 3 252 m against the real 2 778 m, so GRIB temperatures
  are lapse-corrected (6.5 K/km) to the stop and `model_elevation_m` is reported. Open-Meteo does the
  same downscaling server-side from the `elevation` it is sent.
- **eccodes has no macOS wheel.** `eccodes` is only the Python binding. `eccodeslib` supplies the
  library as a wheel on Linux only, so macOS needs `brew install eccodes`. Both live in an optional
  `grib` dependency group; the base install and the whole test suite run without it, and startup
  logs a warning when `WEATHER_SOURCE=grib` has no eccodes to use.
- **Model choice is by lead time.** ICON-CH1 covers up to 30 h ahead (its 33 h horizon less
  publication latency) and ICON-CH2 up to 114 h; anything later is `SourceUnavailable`.

Deferred: **SMN station observations** move to Phase 6 as the live sanity check. No protocol consumes
them yet, and nowcasting against them is a hazard-engine concern.

Tests stay offline. Open-Meteo forecast, ensemble and run metadata, the STAC run listing, a message
search and the collection, and the postcode and `plzDetail` responses are recorded fixtures. The
GRIB source runs end to end (run discovery, per-variable search, download, nearest cell, cache,
fallback to the previous run, pruning) through a fake decoder. The one test that decodes real GRIB
needs `--record` and eccodes.

## Phase 3 - The hazard engine (~6 h) - done

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

### What landed

`SOURCE_MODE=live` now answers `/api/routes/{id}/assessment` from the engine. The same computed
Oeschinensee route, assessed live against Open-Meteo, came back `assessed`: ICON-CH1 for tomorrow,
ICON-CH2 for Saturday, `not_assessable` / `beyond_horizon` two weeks out. A cold request (seven
waypoints × seventeen hours plus the ensemble) takes about two seconds. The only thing flagged was a
morning wind chill below freezing at Hohtürli and the hut, and nowhere lower, which is what the
forecast said.

The engine is split the way routing is. `hazards/` is pure: `terrain.py` (grade, cables and exposure
per stop, from every leg that touches it, return stops included), `rules.py`, `intervals.py`,
`daylight.py`, `alternatives.py` and `engine.py`. `sources/assessor.py` does the fetching, maps
failures to outcomes and caches the result under route + day + model run + `ENGINE_VERSION`. A test
parses both packages and fails if either imports from `sources/`.

The rules, each with an id and version that end up in `provenance`:

| Kind | Rule | Moderate | High |
|---|---|---|---|
| gusts | `WIND-EXP v1` | ≥ 40 km/h exposed (T3+ or cables), ≥ 60 open | ≥ 55 exposed, ≥ 80 open |
| showers | `PRECIP-WET v1` | ≥ 0.5 mm/h on T3+ | ≥ 2 mm/h on T4+ or cables |
| thunder | `THUNDER v1` | ≥ 30 % of members with CAPE ≥ 500 (control CAPE if no ensemble) | ≥ 60 %; one step up above 2 000 m or exposed |
| cold | `COLD-CHILL v1` | wind chill ≤ 0 °C | ≤ −10 °C |
| snow | `SNOW-LEVEL v1` | freezing level at or below the stop | snowline at or below it, with ≥ 0.2 mm falling |
| visibility | `CLOUD-BASE v1` | cloud base below the stop on T3 | on T4+ |
| daylight | `DAYLIGHT v1` | before sunrise; the 45 min before sunset | after sunset |

The day runs from 05:00 to 21:00. Each hour `[h, h+60)` takes the worse of the forecasts at `h` and
`h+60`, because ICON's gusts and precipitation describe the hour *ending* at a time while its
temperature is an instant. Taking both ends is right under either reading. Deviations from the plan
above, and what the plan did not say:

- **`HazardDef.stops` is intervals, and `buildUpFrom` is gone.** A build-up is just a `mod` interval.
  `window` stays, now defined as the hazard's high span, because titles, map notes and the share
  text quote it. The demo data was converted by hand. The frontend's spec-timeline tests (07:30 at a
  cautious pace, 06:30 clearing Hohtürli) pass unchanged against it, which is the check that the
  conversion kept the meaning. Intervals are half-open, so 14:00 exactly now reads as after the gusts.
- **`AssessmentData.conditions`, hourly per stop, replaced `Forecast.feelsLikeC`.** The crux card had
  been inventing its gust figure from the severity (55/40/25 km/h), and a single feels-like number
  cannot be right for an arrival time that moves. A stop that was not evaluated has no conditions,
  so the card says "no data" rather than a guess.
- **`?date=` on the assessment and on retry.** The plan store has always had a date, but nothing
  sent it. `Forecast.unavailableReason` separates `source` from `beyond_horizon`, because "MeteoSwiss
  has been unavailable since…" is untrue of a day no model reaches yet.
- **`notEvaluated` is decided per stop.** A stop is set aside when:
  - any hour's forecast failed, or lacks gusts, precipitation or temperature;
  - the model cell's terrain is more than 500 m off the real height;
  - at an exposed stop, the gust p10–p90 spread is ≥ 25 km/h *and* straddles a threshold.

  A leg is not evaluated if either end is. Following the Phase 2 caveat, spread is read as
  uncertainty and never as bounds on the control value. No stop answering at all is
  `not_assessable`.
- **`altRoute` turns back at the computed bail-out** rather than re-routing. On a hut or pass route
  there is usually no second line to the same place, and turning back always exists. It is offered
  only when something is high at the reference start (07:30, cautious pace, matching the plan
  store) and the shorter day has nothing high. `AltRoute` gained `stopId`, `place` and `grade`.
  `startEarlier` tries −30/−60/−90 min. It picks the smallest shift that lowers the hazard, and
  never one that makes any other hazard worse, the dark included.
- **Warnings raise, they don't replace.** A current (non-outlook) wind, thunderstorm, rain or snow
  warning from the app feed floors that kind at `mod` while it is valid, and says so in provenance.
- **`hasLiftsIf` is false for every computed hazard.** The existing "lifts if" copy has numbers baked
  in, and until Phase 4's `facts` there are no true numbers to put in it. The five new kinds have
  short generic EN/FR copy with no figures.
- **Retry re-checks for real.** It asks for the latest run plus one probe forecast. When the source
  answers, the not-assessable screen refetches the assessment. The demo assessor still answers
  "still down", so the demo keeps its state.

Assumption to revisit: an absent cloud base is read as no ceiling (ICON writes CEILING as undefined
when there is no cloud). A failed fetch never gets that far, because the stop has already been set
aside.

Tests stay offline. The rules are tested at their thresholds, wind chill and sun times against
published tables, and the engine against the showcase route with forecasts written per waypoint and
hour: calm, gusty col, missing stop, missing hour, wide spread, cell height mismatch, warnings, stale
run, both alternatives and their refusals. The assessor is tested against a fake weather source for
failure mapping, caching and recheck, and end to end over the recorded Open-Meteo fixtures in
`test_api_live.py`.

## Phase 4 - Frontend generalisation (~5 h) - done

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

### What landed

A place searched for in live mode can now be routed, assessed, mapped and walked with nothing
hand-authored on the way. Checked against the live services: searching "Oeschinensee" and
"Blüemlisalphütte", then routing between them, gives a 1 370-point route with no `field`. Its assessment
for tomorrow came back `partial` from ICON-CH2, flagging only the dark, with `facts: {sunset: 19:35}`.
Checked in a browser over the demo build: picker → plan → assessment → map → field. The positions were
set through the geolocation override, and no console errors appeared. Deviations from the plan above,
and what it did not say:

- **Two of the five items were already partly there.** Automatic labels landed in Phase 1, and
  `LABEL_POSITION` was already gone. `copy-rules.test.ts` already enforced placeholder parity and
  banned verdict words. What the phase added to it is the part that makes the copy data-driven:
  - no digit in any `hazard.*` string, in either language;
  - every placeholder is one `FACT_PLACEHOLDERS` can fill;
  - every string that needs a fact has a `…Generic` variant that needs none.
- **`facts` are the worst the rule itself flagged, at the stop the hazard is named after.** Taking
  them there, not across the route, keeps `{gust}` and `{place}` in the same sentence true of the
  same place. Hours raised only by a warning contribute no figure, because quoting a calm hour's gust
  next to a warning would contradict the card. A warning-only hazard therefore has `facts=None` and
  renders the generic sentence.
  - `gusts` also carries the threshold it crossed at that stop (exposed or open ground).
  - `showers` carries the wet-rock threshold, so "lifts if" can quote the figure it turns on.
  - `hasLiftsIf` is now true exactly when that figure is known: gusts, showers, cold, snow and
    visibility. It stays false for thunder and daylight.
  - `ENGINE_VERSION` is 2.
- **`i18n/hazardCopy.ts` picks the string, not the caller.** `hazardText(lang, hazard, part)` uses the
  specific key when every placeholder in it has a value, otherwise the generic one. For "lifts if" with
  no generic it returns `null`, and the card leaves the line out. The card, the map's segment notes and
  the share card all go through it; before, each built its own `{from}`/`{to}` params.
  - The demo hazards carry the figures their copy was written with (60/40 km/h at 2 778 m; 1.2 mm with
    the freezing level at 2 900 m).
  - "The 09:00 forecast update" is gone from the copy, because no fact backs it.
- **Recent routes are kept on the device; the endpoint is dropped.** The server has no users. The only
  list it could serve is a scan of its route cache, which would show everyone's searches.
  - `GET /api/recent-routes`, `RouteSource.recent_routes` and the two made-up demo entries (whose ids
    404'd) are removed.
  - The plan store keeps the last five routes picked (persist version 2, migrated). Those, not saved
    plans, are what Recent shows next to the saved plans.
  - Before this, in live mode that endpoint answered 503 and took the whole Plan screen down with it.
- **The picker is `/routes/new`: from, to and one optional via.** Search is debounced 300 ms. A 503
  now carries its `source` in `ApiError`, so the picker can tell "no marked trail connects these"
  (`swisstlm3d`) and "demo mode" apart from an outage.
  - Demo `create_route` returns the showcase route when both ends are its own waypoints, which is all
    demo search offers, so the picker can be walked through offline.
  - The demo waypoints are illustrative: the hand-typed hut sits about 2 km from the gazetteer's, and
    routing live between the demo coordinates fails to snap. Live search results are what to route
    between.
- **Map tiles are swisstopo's `pixelkarte-farbe` over WMTS** (EPSG:3857, JPEG, © swisstopo, zoom
  ≤ 18). They loaded from both this workstation and the browser check.
- **Field mode walks the timeline, not the geometry.**
  - `domain/field.ts` builds a track stop by stop, out and back. It uses the real geometry where legs
    index into it, reversed on the way down, and chords between stops on the demo route, which has no
    geometry.
  - Snapping only searches forward of the furthest progress so far, less 150 m for jitter. That is
    what reads the moraine as the climb in the morning and the descent after the hut; tested both ways.
  - Target is the crux until it is passed, then the end. Remaining time is the rest of the current
    section plus later sections, pace-scaled, with breaks. Distance and ascent are measured along the
    track from the snapped point.
- **`useFieldPosition` wraps `watchPosition`.**
  - Fixes worse than 250 m are ignored.
  - A fix more than 150 m off the line shows an off-route note and holds progress where the hiker left
    the route.
  - Denied, unavailable or still searching falls back to where the plan puts the hiker now, timed from
    when the hike actually started, and says so on screen.
  - The clock is the real one, ticked every 30 s. `route.field`, `FieldPosition` and `fieldEstimate`
    are deleted, and `ROUTE_BUILD_VERSION` is 2.

Not done: there are still no component or screen tests (vitest runs in `node`). The browser check above
was scripted by hand rather than added to the suite. Phase 6's Playwright tests are where it belongs.

## Phase 5 - The AI layer (~6 h) - done

1. **MCP server** (`backend/app/mcp_server.py`, FastMCP) exposing `search_route`,
   `get_route`, `forecast_at`, `assess_route`, so any agent can drive the same engine.
2. **RAG** over a small curated corpus (SAC hiking-scale definitions, MeteoSwiss warning
   semantics, SLF and alpine safety guidance) used to ground the explanations and cite a
   source in `provenance`.
3. **LLM narration** turning computed hazards into prose under strict guard rails:
   numbers come from `facts` and are never generated, verdict words stay banned, and the
   copy-rules test is extended to cover generated text. The rules engine decides; the
   model only phrases. Behind a flag, so a missing key degrades to templated copy.

### What landed

All three parts are in, and all three were checked against running processes: the built app under
uvicorn, a stand-in OpenAI-compatible endpoint, an MCP client over `/mcp`, and the stdio entry point
launched as a subprocess. The Nemotron endpoint itself has not been called yet. See the last point.
What changed from the plan above, and what it did not say:

- **The model is Nemotron, over any OpenAI-compatible endpoint.** The hackathon provides NVIDIA
  Nemotron (~30B) for free, so there is no vendor SDK. `sources/narrator.py` posts to
  `{NARRATION_BASE_URL}/chat/completions` with httpx.
  - **It is hosted on the HP100 instance.** `NARRATION_BASE_URL` points there, and the exact model id
    is whatever that server's `/v1/models` lists. The URL and key are configuration and are not in
    the repo.
  - It asks for JSON-schema output and sends `chat_template_kwargs.enable_thinking=false` plus a
    `/no_think` line, because phrasing needs no reasoning trace.
  - A server that rejects either extra with a 400 or 422 is asked again plainly. A 5xx or a transport
    error is retried once.
  - A `<think>` block or a code fence around the JSON is tolerated.
- **"Numbers come from `facts`" is enforced by a placeholder contract, not by the prompt.**
  - A narrated body may quote a figure only as `{gust}`, `{place}`, `{from}` and so on, and the client
    fills it with the same `hazardParams` the templates use. A body therefore may not contain a digit
    at all, and "never generated" becomes something a regex can check.
  - `narration/guard.py` drops a body that has a digit, a placeholder the hazard has no value for, a
    stray brace, verdict wording or more than 320 characters. Nothing is repaired.
  - Generated text is held to a stricter list than the templates: reassurance in other words ("no real
    risk", "aucun risque") and telling the hiker whether to go.
  - The client checks every body again (`narratedBody` in `i18n/hazardCopy.ts`) with the patterns now
    shared in `i18n/copyRules.ts`.
  - Only the body is narrated. Titles, short lines, "lifts if" and the share text stay templated,
    because they are compact and quote times.
- **Narration is its own endpoint.** `GET /api/routes/{id}/narration?lang=` returns bodies and
  citations, and the assessment request is unchanged. The model never slows the assessment down, a
  failure never touches it, and moving the start time still needs no request. The cards render with
  their templates and swap in a narrated body when one arrives. A narrated card says it was worded by
  a language model.
  - One request covers all of an assessment's hazards in one language. It is cached for 30 minutes
    under the hazards' digest, the language, the model and `PROMPT_VERSION`, with a lock so that the
    web app and an agent asking at once make one call.
- **RAG is 18 hand-written passages and BM25 with tag boosts. There are no embeddings.**
  - Each passage paraphrases a page that was fetched and read while writing it, and links to it. That
    covers the SAC hiking scale PDF, the SAC hiking-safety tips, Suisse Rando's storm and safety pages,
    MeteoSwiss's wind chill and thunderstorm entries, and the federal danger levels.
  - The MeteoSwiss and natural-hazards pages render client-side, so their text could not be read, only
    confirmed to exist. Their passages stick to general meteorology.
  - Two early drafts attributed claims their source does not make (a daylight turnaround rule, and
    summer snow advice pinned on the SLF bulletin). They were rewritten to cite the SAC scale and SAC
    tips, which do say those things.
  - Tags are boosted by specificity: a passage about one hazard outranks one tagged with five.
    Without that, gusts cited the thunderstorm page first.
- **Citations reach `provenance` through a wrapper, not the engine.** `GroundedAssessor` wraps both the
  demo assessor and the engine and appends the top passage's short `cite` ("SAC hiking scale").
  `ENGINE_VERSION`, the engine's cache and its exact-provenance tests are untouched. Citations need no
  model, so they are on whether narration is or not.
- **Layering.** `guidance/` and `narration/` are pure and join `routing/` and `hazards/` in the
  import-graph test. The one piece that calls out, `LlmNarrator`, lives in `sources/` behind a new
  `Narrator` protocol on `Sources`.
- **MCP.** The `mcp` package is 2.x, where FastMCP is now `MCPServer`.
  - The plan's `search_route` became two tools, `search_places` and `create_route`, because a route
    needs two resolved places and an agent should choose between the hits.
  - `search_guidance` was added.
  - `assess_route` returns the assessment together with its narration.
  - The HTTP transport is the SDK's route added to the FastAPI app at exactly `/mcp`, before the
    frontend's catch-all. A mount would match only `/mcp/…` and hand the bare path to the SPA.
  - `host="0.0.0.0"` turns off the SDK's localhost-only Host check, which would reject every request
    that reaches the VM by address.
  - The SDK calls `logging.basicConfig` when a server is built. It is built at WARNING so the service
    log keeps showing what it showed before.
- **Not done: the narration fixture is not a recording yet.** `tests/fixtures/narration_oeschinensee.json`
  holds hand-written stand-in answers, marked `"recorded": false`. The French showers body carries a
  figure on purpose, so the fixture shows the guard dropping it. `pytest --record` with `NARRATION_*`
  set replaces them with the real model's answers. `copy-rules.test.ts` then holds those to the copy
  rules, and `test_narrator.py` checks the fixture's `served` part is exactly what the answers produce.
  Until that runs, how often Nemotron keeps to the no-digit rule is unknown. Every body it breaks costs
  only the phrasing.

Tests stay offline. The frontend has 41 tests and the backend 339.
- Backend: the corpus and retrieval for every hazard kind on every grade; the guard, including French
  word boundaries; the prompt and answer parsing; and the narrator over a scripted endpoint (success,
  a dropped body, reasoning and fences, unreadable answers, 401, timeout, structured output rejected,
  a retried 503, caching, no endpoint, no hazards).
- The API test covers citations in provenance, the narration endpoint and `/mcp` beside the frontend.
  The MCP tools are tested in process over the demo sources, including their errors.
- A pytest reads `hazardCopy.ts` and fails if the placeholder list drifts from the server's.

## Phase 6 - Ops and verification (~3 h)

- An error taxonomy mapping source failures onto `not_assessable` / `partial` / specific
  gaps, so degradation is honest rather than silent.
- Warm the cache for the showcase routes at startup: insurance against a slow GRIB pull
  on stage.
- `scripts/smoke-live.sh` - hits every real source once from the VM and prints what is
  reachable. The only place the blocked-egress gap closes. That includes the Nemotron endpoint on the
  HP100 instance (`/v1/models`, then one tiny chat completion): the app VM reaching HP100 is a network
  path of its own, and nothing else tests it.
- New env vars in `deploy/hiking-safety-assistant.service`; document the eccodes system
  dependency. `NARRATION_BASE_URL` / `NARRATION_MODEL` point at HP100, and the key goes in a
  `systemctl edit` drop-in.
- Record the narration fixture against HP100 (`pytest --record tests/test_narrator.py` with
  `NARRATION_*` set), replacing the hand-written stand-ins, and note how many bodies the guard drops.
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
