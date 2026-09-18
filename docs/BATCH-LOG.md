# Batch log

Scope note (2026-09-14): the UI spec mock-up (docs/ui-spec-mockup.html) has seven screens including
Pre-flight, Field mode, and Share card, which go past the web-only planning slice in ARCHITECTURE.md §2.
The prototype implements them as web screens driven by the same assessment data; field mode is a
lookup-plus-threshold view over the downloaded plan, with no live reasoning, per the mock-up build notes.

## B0 red
tests/unit/test_b0_scaffold.py:7: AttributeError
=========================== short test summary info ============================
FAILED tests/unit/test_b0_scaffold.py::test_package_imports - AttributeError:...
1 failed, 1 skipped in 0.01s
## B0 green
.s                                                                       [100%]
1 passed, 1 skipped in 0.00s
## U1 red
ERROR tests/unit/test_u1_screens.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 warning, 1 error in 0.43s
## U1 green
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
18 passed, 1 skipped, 1 warning in 0.40s
## B1 red
ERROR tests/unit/test_b1_models.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.06s
## B1 green
21 passed, 1 skipped, 1 warning in 0.19s
## B2 red
ERROR tests/unit/test_b2_segmentation.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.08s
## B2 green
24 passed, 1 skipped, 1 warning in 0.16s
## B3 red
ERROR tests/unit/test_b3_swisstopo.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.05s
## B3 green
28 passed, 3 skipped, 1 warning in 2.57s
## B4 red
ERROR tests/unit/test_b4_snapshot.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.05s
## B4 green
32 passed, 3 skipped, 1 warning in 0.19s
## B6 red
ERROR tests/unit/test_b6_warnings.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.05s
## B6 green
34 passed, 3 skipped, 1 warning in 0.19s
## B7 red
ERROR tests/unit/test_b7_rules.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.09s
## B7 green
38 passed, 3 skipped, 1 warning in 0.63s
## B8 red
ERROR tests/unit/test_b8_fusion.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.09s
## B8 green
1 failed, 40 passed, 3 skipped, 1 warning in 0.30s
## B8 fix
The "green: B8" commit landed with one failing test. Cause: the test put precipitation on an ascending
segment, and PRECIP-DESC-01 requires descent >= 200 m; the fixture route is one-way up. The engine was
right; the scenario was wrong. Test now uses COLD-01 (freezing + gust) for the second hazard.
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
## B5 red
ERROR tests/unit/test_b5_meteoswiss.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.05s
## B5 green
1 failed, 43 passed, 6 skipped, 1 warning in 0.32s
## B5 fix
"green: B5" landed with one failure: the default splitter cut the fixture route into six segments while the
scenario assumes the mock-up's three named legs. Fixture now carries breakpoints; adapter honours them.
Live results 2026-09-14: STAC latest_run OK; profile OK; find Wanderland by chmobil_title OK
("Via Alpina (Griesalp - Kandersteg)", grade range resolved); resolve_by_points Oeschinensee→Hohtürli
finds Via Alpina; identify needs tolerance 100 (test updated). Helper fixed: green now refuses to commit a failing suite.
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
## B9 red
ERROR tests/unit/test_b9_postconditions.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.09s
## B9 green
48 passed, 6 skipped, 1 warning in 0.31s
## B10 red
ERROR tests/unit/test_b10_outcomes.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.08s
## B10 green
1 failed, 55 passed, 6 skipped, 1 warning in 0.34s
## B10 fix: test premise (scenario sets fixed_cables as bool; test now makes it Unknown explicitly)
## B10 green
56 passed, 6 skipped, 1 warning in 0.32s
## B11 red
ERROR tests/unit/test_b11_stage1_renderer.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.09s
## B11 green
60 passed, 6 skipped, 1 warning in 0.32s
## B12 red
ERROR tests/unit/test_b12_phrasebank_stage2.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.05s
## B12 green
64 passed, 6 skipped, 1 warning in 0.33s
## B13 red
ERROR tests/unit/test_b13_alternatives.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.09s
## B13 green
1 failed, 69 passed, 6 skipped, 1 warning in 0.50s
## B14 red
ERROR tests/unit/test_b14_corpus.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.05s
## B14 green
2 failed, 71 passed, 6 skipped, 1 warning in 0.37s
## B13/B14 fixes: turnaround mitigation is always offerable (test narrowed to start shifts and alternatives); excerpt text now includes its heading verbatim
## B13 (with B14 corpus heading fix) green
73 passed, 6 skipped, 1 warning in 0.47s
## B15 red
ERROR tests/unit/test_b15_planner.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.05s
## B15 green
78 passed, 7 skipped, 1 warning in 0.37s
## B16 red
ERROR tests/unit/test_b16_pipeline_api.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 warning, 1 error in 0.17s
## B16 green
4 failed, 81 passed, 7 skipped, 1 warning in 0.44s
## B16 fix: fixture route carries per-leg exposure/fixed_cables (pipeline was honestly 'partially assessed' without it); chrome strings marked safe for apostrophes
## B16 green
85 passed, 7 skipped, 1 warning in 0.45s
## B17 red
ERROR tests/golden/test_golden.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.10s
## B17 green
87 passed, 7 skipped, 1 warning in 0.51s
## refactor: demo fidelity (places, second fixture route, demo gust timing); golden snapshot regenerated deliberately; 87 passed, 7 skipped, 1 warning in 0.45s
## L1 red
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.15s
88 passed, 7 skipped, 1 warning in 0.49s
## L2 red
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.10s
1 failed, 89 passed, 7 skipped, 1 warning in 0.49s
90 passed, 7 skipped, 1 warning in 0.45s
## L3 red
FAILED tests/unit/test_l3_stac_paging.py::test_latest_run_uses_range_filter_then_pages_through_all_horizons
1 failed in 0.09s
91 passed, 7 skipped, 1 warning in 0.45s
## L4 red
.                                                                        [100%]
1 passed in 0.11s
92 passed, 7 skipped, 1 warning in 0.50s
## L5 red
FAILED tests/unit/test_l5_not_evaluated_grouping.py::test_not_evaluated_cards_are_grouped_per_leg_with_rules_listed
1 failed in 0.11s
93 passed, 7 skipped, 1 warning in 0.50s

## Live test 2026-09-14 (user request)
Route: Via Alpina (Griesalp - Kandersteg), resolved live on ch.astra.wanderland via chmobil_title; 9 legs, 12.7 km, +1 382 m, trail category Alpinwanderweg at the high point (T4–T6).
Weather: newest ICON-CH1 control run (15:00Z), 7 variables × 13 hours decoded from GRIB2 via eccodes; ~14 s warm, ~35 s cold, 327 MB cache.
Outcome for Tue 15 Sep 07:30 local: partially assessed. Gusts ≤ 17 km/h, 11–18 °C, no precipitation, CAPE ≈ 0 → no hazards. Wind and thunderstorm rules not evaluated on 5 Bergwanderweg legs (exposure unknown from source). Warnings unavailable by design.
Bugs found and fixed by the live run: oldest-run selection (L1), collection chosen from now instead of run reference (L1), UTC vs Europe/Zurich plan time (L2), STAC has no sortby and pages at 100 oldest-first (L3), sub-hour traversal windows lost their hour (L4), 15 ungrouped not-evaluated cards (L5).
Not run: planner live test (no Anthropic credential in the shell).
## L6 red
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.15s
95 passed, 7 skipped, 1 warning in 0.54s
