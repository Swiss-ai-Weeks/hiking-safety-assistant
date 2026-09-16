# Hiking safety assistant

A mobile-first assistant built from the UI spec in [docs/design/](docs/design/hiking-safety-assistant-spec.html). The React frontend (Vite, TypeScript, Tailwind v4) reads everything from a FastAPI backend, which currently serves mock data for the Oeschinensee → Blüemlisalphütte route. The UI is in English and French.

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

Switch between demo states (assessed, partially assessed, not assessable, stale forecast) in Settings, or with `?outcome=partial`, `?outcome=not_assessable` or `?stale=1` on `/assessment`.

### Configuration

The backend reads its settings from the environment, or a `backend/.env` file — see [backend/app/config.py](backend/app/config.py) for every field and its default.

`SOURCE_MODE` picks where data comes from. `demo` (the default) serves the hand-authored Oeschinensee data. `live` routes over the real swisstopo trail network; the forecast and hazard sources fail with a 503 naming the phase that implements them. `/api/health` reports the active mode.

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
| GET | `/api/recent-routes` | Recently checked routes |
| POST | `/api/forecast/retry` | Re-checks the forecast source |

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

The app runs as one systemd service: uvicorn serves the API and the built frontend over plain HTTP on port 8000.

First-time setup, as the user that will run the service (the unit assumes user `hiker` and `/opt/hiking-safety-assistant`; edit [deploy/hiking-safety-assistant.service](deploy/hiking-safety-assistant.service) if yours differ):

```bash
# Prerequisites: git, Node 24 (e.g. via nvm or NodeSource), then pnpm and uv
corepack enable
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/Swiss-ai-Weeks/hiking-safety-assistant.git /opt/hiking-safety-assistant
cd /opt/hiking-safety-assistant
pnpm install --frozen-lockfile
pnpm build
uv sync --directory backend --no-dev --frozen

sudo cp deploy/hiking-safety-assistant.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hiking-safety-assistant
sudo ufw allow 8000/tcp   # or the equivalent for your firewall / security group
```

The app is then at `http://<vm-ip>:8000`.

To deploy a new version, run `./scripts/deploy.sh` on the VM. It pulls, rebuilds, syncs dependencies and restarts the service. Logs: `journalctl -u hiking-safety-assistant -f`.

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