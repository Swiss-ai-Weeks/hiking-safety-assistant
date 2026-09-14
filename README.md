# Hiking Safety Assistant, hackathon slice

Decision-support prototype: swisstopo routes × MeteoSwiss forecasts → segment-level, time-aware hazards,
rendered through reviewed templates. No factual sentence is LLM-generated (KAD-8). See `docs/ARCHITECTURE.md`.

## Run
```bash
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev,grib]"
make test            # 87 unit + golden tests, live tests skipped
make coverage-gate   # EN/DE template coverage + phrase-bank review
make run             # http://127.0.0.1:8000  (demo mode: fixture route, spec-shaped weather)
HSA_LIVE=1 make run  # live mode: api3.geo.admin.ch routes + MeteoSwiss ICON GRIB2 via STAC (downloads ~4 MB per variable-hour)
LIVE=1 make live     # live adapter tests (swisstopo, MeteoSwiss STAC, Anthropic if a credential is set)
```

## Screens
`/` plan · `/assess` assessment (add `&lang=de`) · `/assess?outcome=not_assessable` · `/map` Leaflet route map ·
`/preflight` · `/field` · `/share`. All downstream screens carry `route`, `date`, `start`, `lang` query parameters
and are fed by the same assessment.

## Layout
`src/hsa/{domain,geo,adapters,weather,rules,fusion,gate,planner,corpus,api,eval}`, `templates/{en,de}`, `phrasebank/`,
`tests/{unit,fakes,fixtures,live,golden}`. Batch history with red/green results: `BATCH-LOG.md`.

## What is real and what is fixture
- Real: segmentation, traversal windows, rule catalogue and evaluation, fusion, post-conditions INV-1..3, outcome
  classification, stage 1 and stage 2 gates, EN/DE rendering, mitigations and alternatives, planner boundary,
  corpus excerpts, swisstopo profile/identify/find, MeteoSwiss STAC search and GRIB2 decoding.
- Fixture (demo mode): the Oeschinensee route geometry and per-leg exposure, and the weather field shape.
- Unavailable by design: official warnings feed (disclosed in every response; ARCHITECTURE R-6).
