# Build Plan: Hiking Safety Assistant, hackathon slice
_Derived from ARCHITECTURE.md v0.2 and CONTEXT.md, 2026-09-14. Small batches, TDD red/green, one batch per session._

## How this plan is meant to be run

**One batch per session.** Start a session by reading only: this file's batch card, the ARCHITECTURE.md sections the card names, and CONTEXT.md. Do not load the review log or the requirements unless the card says so.

**Red, then green, then refactor, three commits.**
1. `red: <batch>` writes the tests in the card and runs them. Every new test must fail for the right reason (assertion or missing symbol, not a syntax error). Paste the failing output into `BATCH-LOG.md`.
2. `green: <batch>` writes the least code that passes. Full suite must pass; paste the count.
3. `refactor: <batch>` (optional) with the suite still green.

**Size limits.** A batch touches at most five source files and adds one to four tests. If a card grows past that while you work, stop, split it, and add the new card here before continuing.

**Fakes over mocks.** Every external system (swisstopo, MeteoSwiss STAC, Anthropic) has a fake implementation of the same interface in `tests/fakes/`. Unit tests use fakes. One test per adapter is marked `@pytest.mark.live` and skipped unless `LIVE=1`.

**Fixtures are recorded once.** Batches that need real payloads record them into `tests/fixtures/` with a script in `scripts/record_*.py`, then commit the fixture. Tests never hit the network by default.

**Definition of done for the slice:** batch 17's golden end-to-end test passes on fixtures, `make test` is green, `make coverage-gate` (template coverage) is green for EN and DE, and one live smoke run has been recorded in `BATCH-LOG.md`.

**Layout**
```
hiking-safety-assistant/
  pyproject.toml            # python 3.12, pytest, ruff, fastapi, httpx2, pydantic, shapely, pyproj, anthropic
  Makefile                  # test, live, coverage-gate, run
  src/hsa/
    domain/                 # models, provenance, outcomes
    geo/                    # segmentation, traversal windows
    adapters/               # swisstopo.py, meteoswiss.py, warnings.py, interfaces.py
    weather/                # snapshot, validity
    rules/                  # catalogue loader, rule schema, rules/*.yaml
    fusion/                 # engine, post_conditions, alternatives
    gate/                   # stage1, stage2, renderer, phrase_bank
    planner/                # claude client wrapper, tools, session
    corpus/                 # excerpts, citations
    api/                    # fastapi app, page
    eval/                   # AIQ harness
  templates/{en,de}/        # one file per rule id and per attribute
  phrasebank/{en,de}.yaml
  tests/{unit,fakes,fixtures,live,golden}/
  BATCH-LOG.md
```

---

## Batch cards

### B0 Scaffold and test runner
**Reads:** ARCHITECTURE §2. **Files:** `pyproject.toml`, `Makefile`, `src/hsa/__init__.py`, `tests/conftest.py`.
**Red:** `test_package_imports` (imports `hsa`, asserts `hsa.__version__ == "0.1.0"`); `test_live_marker_skipped_by_default` (a `@live` test is reported as skipped when `LIVE` unset).
**Green:** package, pytest config with the `live` marker, `make test`.
**Done when:** `make test` shows 1 passed, 1 skipped.

### B1 Domain models and provenance
**Reads:** ARCHITECTURE §3, §5; CONTEXT: Source fact and derived fact, Hazard rule. **Files:** `domain/models.py`, `domain/provenance.py`.
**Red:** `test_source_provenance_requires_source_and_timestamp`; `test_derived_provenance_requires_inputs_rule_id_and_version`; `test_hazard_cannot_be_built_without_derived_provenance`.
**Green:** pydantic models: `Route`, `Segment`, `TraversalWindow`, `WeatherCondition`, `Hazard`, `RiskAssessment`, `Recommendation`, `SourceProvenance`, `DerivedProvenance`. Validators enforce the two provenance shapes.

### B2 Segmentation and traversal windows
**Reads:** ARCHITECTURE §5, R-8. **Files:** `geo/segment.py`, `geo/traversal.py`.
**Red:** `test_polyline_with_profile_splits_at_distance_or_elevation_threshold` (a 6 km synthetic line with one 400 m climb yields the expected segment count and boundaries); `test_traversal_windows_are_contiguous_and_monotonic` (start 08:00, pace from a simple ascent-aware formula, windows do not overlap or gap); `test_segment_carries_terrain_attribute_placeholders_as_unknown` (absent attributes are `Unknown`, never `None` or `False`).
**Green:** shapely-based splitter; hiking-time formula documented in the module docstring with its source.

### B3 swisstopo adapter, fake first
**Reads:** ARCHITECTURE §6.2, §11. **Files:** `adapters/interfaces.py`, `adapters/swisstopo.py`, `tests/fakes/swisstopo.py`, `scripts/record_swisstopo.py`.
**Red:** `test_resolve_route_by_name_returns_route_with_geometry_and_grade_range` (fake returns a fixture for one named Wanderland route); `test_resolve_route_by_start_end_returns_network_route_or_unresolved`; `test_unknown_name_yields_unresolved_not_exception`; `tests/live/test_swisstopo_live.py::test_profile_service_returns_dist_and_alts` (`@live`).
**Green:** `RouteSource` protocol; real adapter against api3.geo.admin.ch (find on `ch.astra.wanderland`, identify on `ch.swisstopo.swisstlm3d-wanderwege`, profile service); trail category mapped to T-grade range T1 / T2-T3 / T4-T6. Record one route fixture. **Verify-first:** the live test is the verification for §11 rows 1 to 3; log the outcome in BATCH-LOG.

### B4 Weather snapshot and validity
**Reads:** ARCHITECTURE §6.3; CONTEXT: Weather snapshot. **Files:** `weather/snapshot.py`.
**Red:** `test_snapshot_key_is_route_date_forecast_window`; `test_changing_start_time_invalidates_snapshot`; `test_expired_ttl_invalidates_snapshot`; `test_snapshot_is_never_persisted` (no `save`/`to_disk` API; in-memory store only).
**Green:** `WeatherSnapshot`, `SnapshotKey`, `SnapshotStore` with `get_valid_or_none`.

### B5 MeteoSwiss adapter: STAC lookup and GRIB extraction
**Reads:** ARCHITECTURE §6.3, R-7, R-8. **Files:** `adapters/meteoswiss.py`, `tests/fakes/meteoswiss.py`, `scripts/record_meteoswiss.py`, `tests/fixtures/icon_ch1_crop.grib2`.
**Red:** `test_selects_ch1_within_33h_and_ch2_beyond`; `test_extracts_condition_per_segment_per_hour_from_fixture` (cropped GRIB yields temperature, precipitation, gust for three segment centroids over four hours); `test_missing_variable_marks_condition_field_not_evaluated`; `tests/live/test_meteoswiss_live.py::test_stac_search_returns_latest_ch1_assets` (`@live`).
**Green:** STAC search against `ch.meteoschweiz.ogd-forecasting-icon-ch1` / `-ch2`; GRIB2 decode with the library chosen in this batch (candidates: meteodata-lab, earthkit-data, cfgrib; pick the one that opens the fixture); nearest-cell lookup; freezing-level derivation documented. **This is the riskiest batch.** If the fixture cannot be produced in one session, split: B5a STAC and asset selection with a fake; B5b GRIB extraction.

### B6 Warnings adapter: unavailable by design
**Reads:** ARCHITECTURE §7 "Warnings in the slice", R-6. **Files:** `adapters/warnings.py`.
**Red:** `test_warnings_source_reports_unavailable_with_reason`; `test_unavailable_warnings_yield_disclosure_object_not_empty_list`.
**Green:** `WarningsSource` protocol with `UnavailableWarnings` implementation returning a `WarningsStatus(available=False, reason=..., channels=[MeteoSwiss, SLF])`.

### B7 Hazard rule catalogue
**Reads:** ARCHITECTURE §6.4; CONTEXT: Hazard rule, Explanation template. **Files:** `rules/schema.py`, `rules/loader.py`, `rules/rules/exposed_ridge_high_gust.yaml`, `rules/rules/thunderstorm_window.yaml`, `templates/en/`, `templates/de/`.
**Red:** `test_rule_requires_id_version_inputs_condition_severity_justification_basis`; `test_loader_rejects_rule_missing_template_for_enabled_language`; `test_rule_with_missing_required_input_returns_not_evaluated`.
**Green:** YAML schema; loader; two seed rules with EN and DE templates and cited basis. `make coverage-gate` implemented here.

### B8 Fusion engine core
**Reads:** ARCHITECTURE §6.4, §5. **Files:** `fusion/engine.py`, `fusion/confidence.py`.
**Red:** `test_exposed_segment_with_high_gust_in_window_yields_hazard_with_rule_id_and_inputs`; `test_hazard_confidence_falls_with_data_age_and_lead_time`; `test_assessment_aggregates_hazards_and_carries_reasoning_trace_from_derived_provenance`.
**Green:** `assess(route, plan, snapshot, warnings, capability) -> RiskAssessment`; confidence function documented.

### B9 Fusion post-conditions INV-1..3
**Reads:** ARCHITECTURE §7. **Files:** `fusion/post_conditions.py`.
**Red:** `test_INV1_recommendation_without_justifying_hazard_is_dropped`; `test_INV2_official_warning_subordinates_derived_hazard_in_same_category` (uses a fake available warnings source); `test_INV2_is_inert_when_warnings_unavailable_and_disclosure_present`; `test_INV3_assessment_with_evidence_free_hazard_is_not_produced`.
**Green:** post-condition pipeline; repaired vs fatal semantics per CONTEXT.

### B10 Assessment outcomes
**Reads:** ARCHITECTURE §8; CONTEXT: Assessment outcome. **Files:** `domain/outcome.py`, `fusion/coverage.py`.
**Red:** `test_not_assessable_when_weather_unavailable`; `test_partially_assessed_when_one_rule_on_one_segment_lacks_input`; `test_assessed_when_all_applicable_rules_evaluated`; `test_missing_capability_uses_conservative_default_and_stays_assessed`; `test_empty_hazard_list_only_reported_under_assessed`; `test_unknown_unused_attribute_goes_to_not_available_list_not_outcome`.
**Green:** outcome classifier with precedence.

### B11 Output gate stage 1 and template renderer
**Reads:** ARCHITECTURE §6.5, INV-4, INV-5. **Files:** `gate/stage1.py`, `gate/renderer.py`.
**Red:** `test_INV4_stale_forecast_caps_confidence_and_attaches_label`; `test_INV5_low_confidence_sets_cautionary_framing`; `test_renderer_produces_en_and_de_sentence_for_seed_rule_with_slots_filled`; `test_renderer_falls_back_to_en_with_notice_when_de_template_missing`.
**Green:** stage 1; renderer reading `templates/{lang}/{rule_id}.txt` with typed slots.

### B12 Phrase bank and output gate stage 2
**Reads:** ARCHITECTURE §6.5, INV-6, INV-7. **Files:** `gate/phrase_bank.py`, `gate/stage2.py`, `phrasebank/en.yaml`, `phrasebank/de.yaml`.
**Red:** `test_stage2_rejects_sentence_not_in_phrase_bank`; `test_INV6_phrase_bank_review_fails_on_verdict_pattern` (a test phrase "you are good to go" fails the review); `test_INV7_response_held_until_disclaimer_block_attached`; `test_wrapper_assembly_from_identifiers_yields_only_bank_sentences`.
**Green:** phrase bank loader; review function run in `make coverage-gate`; stage 2.

### B13 Mitigations and alternatives
**Reads:** ARCHITECTURE §8. **Files:** `fusion/alternatives.py`.
**Red:** `test_shifted_start_that_removes_hazard_is_offered_as_mitigation`; `test_shifted_start_that_adds_equal_hazard_is_not_offered`; `test_candidate_with_grade_upper_bound_above_L_is_ineligible`; `test_unknown_grade_candidate_never_auto_proposed`; `test_candidate_gets_own_snapshot_and_plan`; `test_no_qualifying_option_yields_explicit_none_found_with_channels`.
**Green:** mitigations, candidate retrieval via `RouteSource.candidates_near`, eligibility limit L, comparison. Constants N, radius, threshold in one config module.

### B14 Retrieval corpus and cited excerpts
**Reads:** ARCHITECTURE §6.2. **Files:** `corpus/store.py`, `corpus/excerpt.py`, `corpus/data/sac_scale.md`.
**Red:** `test_lookup_returns_verbatim_passage_with_source_and_timestamp`; `test_excerpt_text_is_byte_identical_to_corpus_chunk`; `test_no_match_returns_empty_not_generated_text`.
**Green:** small chunked corpus, keyword or embedding lookup (keyword is enough for the slice), `CitedExcerpt`.

### B15 Query planner with Claude
**Reads:** ARCHITECTURE §6.1; the claude-api skill notes in BATCH-LOG (model `claude-opus-5`, adaptive thinking, strict tools, structured output, streaming for long output). **Files:** `planner/tools.py`, `planner/planner.py`, `planner/session.py`, `tests/fakes/anthropic.py`.
**Red:** `test_planner_calls_resolve_route_then_assess_for_a_planning_question` (fake client scripted tool calls); `test_planner_output_is_only_tool_calls_and_phrase_ids_never_free_text_to_user`; `test_session_retains_hike_plan_across_turns`; `tests/live/test_planner_live.py::test_one_real_call_returns_tool_use` (`@live`).
**Green:** tool definitions with `strict: true`; planner loop; phrase-id selection via structured output; session store keyed by hike plan.

### B16 API and web page, staged response
**Reads:** ARCHITECTURE §4, §9. **Files:** `api/app.py`, `api/templates/page.html`.
**Red:** `test_post_plan_returns_assessment_block_first_with_outcome_and_invariant_ids`; `test_response_contains_disclaimer_block`; `test_assessment_path_under_budget_with_fakes` (asserts the fake-backed assessment path completes under a configured budget, as a regression guard, not a real latency proof); `test_language_switch_to_de_renders_de_templates`.
**Green:** FastAPI routes `POST /plan`, `POST /ask`; server-rendered page; block ordering.

### B17 AIQ harness and golden end-to-end
**Reads:** ARCHITECTURE §6.1 evaluation, §8. **Files:** `eval/harness.py`, `tests/golden/cases.yaml`, `tests/golden/test_golden.py`.
**Red:** `test_harness_scores_three_golden_cases_for_decomposition_and_excerpt_relevance`; `test_golden_planning_scenario_matches_snapshot` (one route, one date, fixtures; snapshot of the rendered blocks, EN and DE).
**Green:** harness; golden snapshot committed. Run one `LIVE=1` pass and record in BATCH-LOG.

---

## Batch order and dependencies

```
B0 → B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8 → B9 → B10 → B11 → B12 → B13 → B14 → B15 → B16 → B17
```
B3, B5, B6, B14 can be pulled forward or parallelised across people after B1. B15 needs B12 and B14. B16 needs B15. B17 needs everything.

## Open items to resolve during the build (log answers in BATCH-LOG.md)
- B3: which api3.geo.admin.ch endpoints and layer attributes actually exist for name resolution, start/end routing, and exposure. Update ARCHITECTURE §11 statuses.
- B5: GRIB library choice; which ICON surface parameters are published; whether a nowcast product exists.
- B7: who authors and reviews the first rules and templates (R-9).
- B13: values for N, radius, and the severity threshold.
- B15: `ant auth status` or `ANTHROPIC_API_KEY` availability for the live smoke.

## Not in this plan
Phone or watch clients, offline snapshot, GPX/drawn-track/region input, meteoblue, FR/IT templates, satellite comms or SOS, MCP server packaging (tools are in-process for the slice), deployment beyond `make run` on a laptop.
