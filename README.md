# Hiking safety assistant

A mobile-first assistant built from the UI spec in [docs/design/](docs/design/hiking-safety-assistant-spec.html). The React frontend (Vite, TypeScript, Tailwind v4) reads everything from a FastAPI backend that routes over swisstopo's trail network, reads MeteoSwiss ICON forecasts, runs a hazard engine over them and lets you ask Nemotron about the hike. The UI is in English and French.

**Live:** https://hiking-safety.tail685478.ts.net

| Folder | Contents |
|---|---|
| [frontend/](frontend/) | React app |
| [backend/](backend/) | FastAPI app (Python 3.13, managed with uv) |
| [deploy/](deploy/), [scripts/](scripts/) | systemd unit and update script for the VM |

### Run locally

Needs Node 24 with pnpm, and [uv](https://docs.astral.sh/uv/) (`brew install uv`). uv installs Python and the backend dependencies by itself.

```bash
pnpm install
pnpm dev      # frontend on http://localhost:5173 with the API on :8000, both hot-reloading
pnpm test     # vitest + pytest
pnpm lint     # eslint + ruff
pnpm start    # production build served by the backend on http://localhost:8000
```

In dev, Vite proxies `/api` to the backend. In production the backend serves the built frontend and the API from one port.

Under `SOURCE_MODE=demo`, switch between demo states (assessed, partially assessed, not assessable, stale forecast) in Settings, or with `?outcome=partial`, `?outcome=not_assessable` or `?stale=1` on `/briefing`.

### Configuration

The backend reads its settings from the environment, or a `backend/.env` file — see [backend/app/config.py](backend/app/config.py) for every field and its default.

`SOURCE_MODE` picks where data comes from. `demo` (the default) serves the hand-authored Oeschinensee data. `live` routes over the real swisstopo trail network, reads real MeteoSwiss forecasts and runs the hazard engine over them. `/api/health` reports the active mode.

### Weather data

Under `SOURCE_MODE=live`, `WEATHER_SOURCE` picks one of two implementations of the same model, MeteoSwiss ICON-CH1 (1 km, next 33 h) and ICON-CH2 (beyond that, up to 5 days):

- `grib` (the default) reads the official GRIB2 files from MeteoSwiss Open Government Data. It needs eccodes:
  ```sh
  brew install eccodes          # macOS only; on Linux the `eccodeslib` wheel supplies the library
  cd backend && uv sync --group grib
  ```
  The first forecast downloads the grid constants (34 MB) and about 25 MB of messages per forecast hour, which takes a minute. After that, later stops and hours come from the cache. Messages from superseded runs are deleted.
- `open-meteo` serves the same ICON fields as JSON through [Open-Meteo](https://open-meteo.com/), with nothing to install. Switch to it if eccodes cannot be installed.

Ensemble spread (10th and 90th percentile of gusts and precipitation, and thunderstorm potential from CAPE) comes from Open-Meteo's ensemble API for both sources. As GRIB it would be ten times the download.

MeteoSwiss publishes no weather warnings as open data. `METEOSWISS_APP_WARNINGS=true` reads them from the undocumented API behind the MeteoSwiss app, and marks each one unofficial. Off (the default), warnings stay a reported gap rather than an empty all-clear.

### AI layer

The rules engine decides every hazard. The AI layer grounds, phrases and exposes those decisions. It never makes one.

**Guidance and citations.** [backend/app/guidance/corpus/](backend/app/guidance/corpus/) holds 18 short passages in our own words, each paraphrasing a page it links to: the SAC Mountain and Alpine Hiking Scale, SAC and Suisse Rando safety advice, MeteoSwiss and the federal danger levels. BM25 retrieval, boosted by each passage's hazard-kind and grade tags, picks the passages for each hazard. The top one is appended to its `provenance`, and all of them come back from `/narration` as links. This needs no model and no key.

**Narration.** Off by default. Any OpenAI-compatible chat completions endpoint works (vLLM, NVIDIA NIM, …):

```sh
NARRATION_ENABLED=true
NARRATION_BASE_URL=https://…/v1        # `/chat/completions` is appended
NARRATION_API_KEY=…
NARRATION_MODEL=nvidia/nemotron-3-nano-30b-a3b
NARRATION_THINKING=false               # sends /no_think and enable_thinking=false
```

The model rewrites each hazard's body using the retrieved passages. It may quote a figure only as a placeholder (`{gust} km/h`), and the client fills those from the engine's `facts`, so a narrated body may not contain a digit at all. [backend/app/narration/guard.py](backend/app/narration/guard.py) drops any body that has a digit or a placeholder the hazard cannot fill, or that uses verdict wording (the UI's banned words plus a stricter list for generated text). The client checks it again before showing it. A dropped body, a timeout or a bad key cost that phrasing only: the card shows its template. A narrated card says it was worded by a language model. One request covers every hazard in an assessment, per language, and the result is cached for 30 minutes.

`pytest --record` with those variables set re-records `backend/tests/fixtures/narration_oeschinensee.json` from the real model; it is recorded from Nemotron 3.5 Lightning. `copy-rules.test.ts` holds what it serves to the same rules as the templates. A body the guard rejects is sent back once with its reasons; over 20 fresh requests 30 of 30 bodies were served.

**Questions ("Ask Nemotron").** A text field is always on screen in the briefing and in field mode. A question is answered from a briefing the server writes out of the assessment, the hiker's plan (arrival at each stop at their pace) and, on the trail, where they are and what their rule says, plus the guidance passages retrieved for the question. Every figure in that briefing is a placeholder with its value and unit (`{wx.hohturli.gust} = 40 km/h`). An answer may quote a figure only as such a placeholder or as that exact value with that unit, so no number in it is the model's own; it may give no verdict (the same banned wording as narration) and is sent back once with its reasons if it breaks a rule. Up to four earlier exchanges ride along. Planning questions are cached for 30 minutes, questions during a hike never; each client gets 10 a minute. Against Nemotron 3.5 Lightning, 40 test questions gave 35 answers, 5 correct off-topic refusals and no dropped answers. Known limit: a real figure can still be attributed to the wrong stop or hour.

Anything a model wrote carries a sparkle **Nemotron** badge in its own colour, which is neither a severity nor the action colour.

**MCP server.** The engine as tools for any agent: `search_places`, `create_route`, `get_route`, `forecast_at`, `assess_route` (assessment plus citations and narration), `ask_about_route` and `search_guidance`. They call the same sources in process, so the caches are shared and the shapes match `/api`.

```sh
claude mcp add hiking-safety -- uv run --directory "$PWD/backend" python -m app.mcp_server   # stdio
claude mcp add --transport http hiking-safety http://localhost:8000/mcp                     # the running app
```

The running app serves `/mcp` unless `MCP_HTTP=false`. It has no authentication, like the rest of the API.

### Trail data

`SOURCE_MODE=live` routes over [swissTLM3D Wanderwege](https://www.swisstopo.admin.ch/en/landscape-model-swisstlm3d), the official Swiss hiking network. It is a 190 MB download, prepared once:

```bash
uv run --directory backend python -m scripts.fetch_trails     # ~190 MB from swisstopo, checksum verified
unzip -d backend/data backend/data/swisstlm3d-wanderwege.gpkg.zip
uv run --directory backend python -m scripts.import_trails    # clip, snap and index -> backend/data/trails.sqlite
```

The import keeps only `TRAILS_BBOX` (the Bernese Oberland by default) and writes a small SQLite graph — 59,000 edges, 64 MB, loaded in under three seconds at startup. Widen the box to route elsewhere:

```bash
uv run --directory backend python -m scripts.import_trails --bbox 2600000,1150000,2700000,1250000
```

Both files are gitignored. Without them, `POST /api/routes` answers 503 and says which command to run.

The frontend types are checked against the backend's schema rather than kept in step by hand. After changing [backend/app/models.py](backend/app/models.py):

```bash
pnpm gen:api   # backend/openapi.json + frontend/src/api/schema.d.ts, both committed
```

A rename then fails `pytest` (the schema snapshot is stale) and `tsc -b` (the assertions in [frontend/src/api/contract.ts](frontend/src/api/contract.ts)). `frontend/src/domain/types.ts` stays hand-written; the generated schema is what it is checked against.

### API

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{"status": "ok", "mode": "demo"}` — `mode` is the active `SOURCE_MODE` |
| GET | `/api/routes/search?q=` | Place-name search (swisstopo gazetteer), for picking the ends of a route |
| POST | `/api/routes` | Routes `{from, to, via?}` over swissTLM3D. The id it returns is a digest of the request, so the same search is always the same route |
| GET | `/api/routes/{routeId}` | Route geometry, stops and legs |
| GET | `/api/routes/{routeId}/assessment?scenario=assessed` | Forecast, hazards, gaps and alternatives (`assessed`, `partial`, `not_assessable`, `stale`) |
| GET | `/api/routes/{routeId}/narration?scenario=&date=&lang=en` | The assessment's hazards phrased by a language model (when configured), and the guidance each is grounded in |
| POST | `/api/routes/{routeId}/ask?scenario=&date=&lang=` | `{question, history?, plan?, live?}` → a language model's answer from the assessment, the plan and (during a hike) where you are. Figures are filled in by the server; `reason` says why there is no text |
| POST | `/api/forecast/retry` | Re-checks the forecast source |
| POST | `/mcp` | The MCP server over streamable HTTP (see [AI layer](#ai-layer)) |

Interactive docs are at `/docs` while the backend runs.

A computed route is held in the backend's disk cache for 30 days. After that `GET /api/routes/{id}` is a 404 and the app offers the demo route instead, so a saved link degrades rather than breaking. Open one in the UI with `?routeId=`:

```bash
curl -s -X POST localhost:8000/api/routes -H 'content-type: application/json' \
  -d '{"from":{"name":"Oeschinensee","latLng":[46.49836,7.72667]},
       "to":{"name":"Blüemlisalphütte","latLng":[46.51019,7.77162]}}' | jq -r .id
# then http://localhost:5173/?routeId=<id>
```

### Where the numbers come from

Nothing on a computed route is hand-written. Distances, ascent and `legMinutes` follow from four sources, each of which degrades on its own — a source that cannot answer costs detail, not the route:

| Source | What it decides |
|---|---|
| swissTLM3D Wanderwege | The line itself, and the official trail class (`Wanderweg` → T1, `Bergwanderweg` → T2, `Alpinwanderweg` → T4) on every segment |
| swissALTI3D (`profile.json`) | Elevation along the chosen line, and so ascent, descent and per-leg climb |
| OpenStreetMap (Overpass) | Refines the grade within a class via `sac_scale`, and the `cables` flag via `safety_rope` / `ladder` / `via_ferrata_scale`. It can raise a grade but never lower it, and only where several samples along the leg agree; a leg it cannot corroborate is marked `gradeEstimated` |
| swissnames3d | The names the stops are called after — passes, huts, lakes — so the timeline reads in places rather than coordinates |

Walking time is the SAC / DIN 33466 estimate (`backend/app/routing/timing.py`): 4 km/h on the flat, 400 m/h up, 800 m/h down, the larger effort counted in full and the smaller halved, then penalised by grade. Dijkstra weights the graph by *that*, not by distance, so the routing itself prefers the line a person would choose.

### Deploy to the VM

The live app is **https://hiking-safety.tail685478.ts.net**: one systemd service (uvicorn serving the API, the built frontend and `/mcp`) on `127.0.0.1:8100`, published over HTTPS with Tailscale Funnel. Port 8000 on the same machine is vLLM serving Nemotron, which the app calls for narration and questions.

First-time setup, as the user that will run the service (the unit assumes user `hiker` and `/opt/hiking-safety-assistant`; edit [deploy/hiking-safety-assistant.service](deploy/hiking-safety-assistant.service) if yours differ):

```bash
# Prerequisites: git, Node 24 (e.g. via nvm or NodeSource), then pnpm and uv
corepack enable
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/Swiss-ai-Weeks/hiking-safety-assistant.git /opt/hiking-safety-assistant
cd /opt/hiking-safety-assistant
pnpm install --frozen-lockfile
pnpm build
uv sync --directory backend --no-dev --frozen   # add `--group grib` for WEATHER_SOURCE=grib (needs eccodes, see Weather data)
# the trail graph, once (see Trail data)

sudo cp deploy/hiking-safety-assistant.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hiking-safety-assistant
sudo tailscale funnel --bg 8100   # public HTTPS; or put any reverse proxy in front of :8100
```

Then check that the VM reaches every source, the model and the app itself:

```bash
./scripts/smoke-live.sh --app https://hiking-safety.tail685478.ts.net
```

It prints one line per check (swisstopo search, elevation, names and tiles; Overpass; Open-Meteo and MeteoSwiss STAC runs with **their age and whether they reach tomorrow's hike**; an SMN station; app warnings; the model's `/models` and a one-line completion; the app's health, assessment, narration, questions and MCP) and exits non-zero if a required one fails.

To deploy a new version, run `./scripts/deploy.sh` on the VM. It pulls, rebuilds, syncs dependencies and restarts the service. Logs: `journalctl -u hiking-safety-assistant -f`; warm-up lines appear there after a restart.

### How failures degrade

Nothing a source does can take a page down. Each failure costs what it has to and says so:

| What fails | What the hiker sees |
|---|---|
| Place search, trail graph, elevation (routing) | 503 naming the source; the picker says which ("no marked trail connects these", or an outage) |
| OSM grades, swissNAMES3D | The route still computes; grades fall back to the official class (`gradeEstimated`), stops are named generically |
| Forecast run unavailable | `not_assessable` / `source`, with the official links and a retry |
| Day beyond every model's reach | `not_assessable` / `beyond_horizon` |
| Newest fine model run published late | The coarser model serves the whole day rather than leaving hours out |
| One stop's forecast, or a wide ensemble spread there | `partial`: those legs are "not evaluated", never shown as clear |
| Warnings feed | A `warnings` gap, never an empty all-clear |
| Any other error inside an assessment | `not_assessable`, logged with a stack trace, not cached |
| The language model (narration) | The hazard card keeps its template |
| The language model (questions) | A fixed sentence for `unavailable`, `dropped` or `disabled` |

### End-to-end tests

```bash
pnpm e2e                                                    # build, then Playwright over a demo-mode server
E2E_BASE_URL=https://hiking-safety.tail685478.ts.net pnpm -C frontend exec playwright test   # the live app
```

The first run needs `pnpm -C frontend exec playwright install chromium`.

---

### Original
- **Description:** Leverage public swiss data on weather and hiking routes to create an assistant.
- **Tools:** RAG, MCP, AIQ
- **Difficulty:** Hard
- **Data:** Open Data (OGD) - MeteoSwiss and https://www.swisstopo.admin.ch/en
- **GitHub:** https://github.com/Swiss-ai-Weeks/hiking-safety-assistant

---

### Summary
Can AI help people make better decisions in the mountains? Build an assistant that combines information about Swiss hiking routes, terrain, and weather to help users understand the conditions of a planned hike. The challenge is deliberately open: your assistant might answer questions before a hike, provide context during a route, identify potential risks, or suggest alternatives. The key is to combine different sources of information into useful, context-aware guidance.

### Detailed
Build an AI assistant that combines Swiss hiking-route and weather information to help users assess and understand hiking conditions. A user might ask about a planned route, current or forecast conditions, potential risks, or whether alternative routes could be more appropriate. Solutions should combine information from multiple sources and ideally be capable of adapting recommendations to the specific route and conditions rather than simply returning weather or map information. Relevant public data is available from MeteoSwiss Open Data and swisstopo.

Participants can explore RAG, MCP, agentic workflows, geospatial reasoning, or combinations of these approaches. Suggested technologies include RAG, MCP, and AIQ.