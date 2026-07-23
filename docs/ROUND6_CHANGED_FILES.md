# Round 6 — Changed Files

Generated: 2026-07-23   Base commit: 5516209 (before round 6)   Head: work-streams A + B + Y complete — `git diff --name-status -M 5516209..HEAD` is the authority

Derived from `git diff --name-status 5516209..HEAD`. The operator copies files
from this list literally into the client environment; nothing outside it
changed. Nothing under `data/real/` is touched by this round (the real data set
is rebuilt on the client machine by `scripts/build_real_data.py`).

## Copy these to the client environment

### Work-stream A — attribution correctness

| File | Change | Why |
|---|---|---|
| app/v2/drivers/attribution.py | MODIFIED | A1 recurring gate; A2 persistence rule over the full loaded range; A3 BASELINE_LIMITED bounded + AttributionError; test-only legacy path |
| app/v2/dataset/builder.py | MODIFIED | passes loaded months + ACCOUNT_ABSENCE_MONTHS; presence summary (new/lost/BL per transition); driver_cause seed wording; anomaly workflow CSVs (Y) |
| app/config/settings.py | MODIFIED | ACCOUNT_ABSENCE_MONTHS (A2) + ANOMALY_* thresholds (Y2) |
| .env.example | MODIFIED | ACCOUNT_ABSENCE_MONTHS + ANOMALY_* keys ⚠ merge into the client's .env by hand — do not overwrite it |
| scripts/build_real_data.py | MODIFIED | passes absence months; STOPs on AttributionError; summary prints MIX% + new/lost + BL per transition (A4.5) |
| scripts/generate_sample_data.py | MODIFIED | account stories moved to the persistence rule; intermittency story added |
| scripts/verify_attribution.py | **NEW** | A4 bug-repro fixture + automated gates (MIX <15%, recurring-only, persistence, BL bound) |
| app/agents/nodes/commentary_agent.py | MODIFIED | A5 precise account-rule wording in prompt + fallbacks; Y6 narrate_anomaly + rule meanings |
| app/agents/nodes/explainability_agent.py | MODIFIED | A5 why-this-cause / order / description texts state the precise rule |
| frontend/components/patterns/revenue-driver-glossary.tsx | MODIFIED | A5 New/Lost Account + Baseline Period Limit glossary entries |
| frontend/components/ai-insights/commentary-cards.tsx | MODIFIED | A5/R6 baseline note covers BOTH edges of the loaded range |
| docs/SOLUTION_GUIDE.md | MODIFIED | A5 §6.3/§6.4 precise rule + refreshed worked examples |

### Work-stream B — carry-overs

| File | Change | Why |
|---|---|---|
| docs/tigergraph_foundation/tigergraph/schema/90_drop_all.gsql | MODIFIED | B1 regenerated: queries→graph→reverse edges→forward edges→vertices; NEEDS-LIVE-VERIFICATION header ⚠ run this on the live box as part of acceptance |
| scripts/generate_schema_artifacts.py | MODIFIED | B1 drop script now generated from the schema + query catalog (cannot drift) |

### Work-stream Y — anomaly detection

| File | Change | Why |
|---|---|---|
| docs/tigergraph_foundation/tigergraph/schema/01_vertices.gsql | MODIFIED | Y1 phx_dm_v2_anomaly + phx_dm_v2_anomaly_scan ⚠ live schema change — re-run DDL + 03_create_graph on the client box |
| docs/tigergraph_foundation/tigergraph/schema/02_edges.gsql | MODIFIED | Y1 anomaly_for_advisor / anomaly_in_scan / anomaly_cites_driver ⚠ live schema change |
| docs/tigergraph_foundation/tigergraph/schema/03_create_graph.gsql | MODIFIED | Y1 new types in the graph ⚠ live schema change |
| docs/tigergraph_foundation/tigergraph/schema/schema_catalog.json | MODIFIED | regenerated (20 vertices / 30 edges) |
| docs/tigergraph_foundation/tigergraph/loading/jobs/load_v2_all.gsql | MODIFIED | regenerated with anomaly files |
| docs/tigergraph_foundation/data/manifest.json | MODIFIED | anomaly workflow CSVs (header-only, additive) ⚠ conflict-risk: build_real_data.py rewrites this with real counts on the client machine — copy BEFORE rebuilding the real set |
| docs/tigergraph_foundation/tigergraph/queries/GQ-018_get_anomalies.gsql | **NEW** | Y3 retrieval query ⚠ NEEDS-LIVE-INSTALL |
| docs/tigergraph_foundation/tigergraph/queries/GQ-019_get_anomaly_scans.gsql | **NEW** | Y3 scan history ⚠ NEEDS-LIVE-INSTALL |
| docs/tigergraph_foundation/tigergraph/queries/query_catalog.json | MODIFIED | GQ-018/019 entries |
| docs/tigergraph_foundation/tigergraph/queries/install_all_queries.gsql | MODIFIED | + GQ-018/019 |
| docs/tigergraph_foundation/tigergraph/queries/tests/query_cases.json | MODIFIED | + get_anomalies / get_anomaly_scans cases |
| app/graph/queries/common.py | MODIFIED | ANOMALY / ANOMALY_SCAN vertex constants |
| app/graph/queries/v2.py | MODIFIED | local-tier impls of GQ-018/019 |
| app/guardrails/numeric_validation.py | MODIFIED | Y6 validate_anomaly_text (no-invented-figures for anomaly wording) |
| app/v2/anomalies/__init__.py | **NEW** | Y package |
| app/v2/anomalies/detection.py | **NEW** | Y2/Y5 six rules, batch scan, additive scan_ids, CLI |
| app/v2/anomalies/service.py | **NEW** | retrieval service (severity ranking) |
| app/api/routers/v2.py | MODIFIED | GET /anomalies, /anomalies/scans, POST /anomalies/scan, scan/status |
| scripts/verify_anomalies.py | **NEW** | Y8 per-rule fixtures, guardrail negatives, additive re-scan proof |
| frontend/app/(dashboard)/anomalies/page.tsx | **NEW** | Y7 screen per roadmap mockup |
| frontend/lib/api/v2.ts | MODIFIED | anomaly types + API methods |
| frontend/components/layout/v2-shell.tsx | MODIFIED | Anomalies tab in Results sub-nav |
| frontend/lib/navigation.ts | MODIFIED | Anomalies sidebar entry |
| frontend/components/navigation/sidebar-navigation.tsx | MODIFIED | AlertTriangle icon registered |

### Sample data set (test asset — copy only if the client environment keeps a sample set)

`data/sample/**` — regenerated for the round-6 account stories plus commentary
v14 and anomaly scan001 (33 modified + 5 new anomaly CSVs). The real data set is
NOT shipped; it is rebuilt on the client machine.

### Docs / tracking (no runtime effect)

BUILD_REPORT.md · PROGRESS.md · docs/ROUND6_CHANGED_FILES.md

## Conflict-risk files (flagged above with ⚠)

- `.env.example` — merge new keys into the client's `.env` by hand; never overwrite the operator's `.env`.
- `docs/tigergraph_foundation/data/manifest.json` — rewritten by `build_real_data.py` with real counts; copy this file first, then rebuild.
- Schema DDL + `90_drop_all.gsql` + GQ-018/019 — parse-reasoned only, flagged NEEDS-LIVE-VERIFICATION / NEEDS-LIVE-INSTALL; running them on the live box is part of operator acceptance.
