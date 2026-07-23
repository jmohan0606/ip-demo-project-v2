# Round 5 — Changed Files
Generated: 2026-07-23T10:35:00Z   Base commit: ea57f3c (before round 5)   Head: (work-stream B) — see git log

Derived from `git diff --name-status ea57f3c..HEAD` — updated after each
work-stream's commit. The operator copies files from this list literally into the
client environment; nothing outside it changed.

## Copy these to the client environment

### Backend (work-stream A)
| File | Change | Why |
|---|---|---|
| app/graph/client.py | MODIFIED | A1 fail-loud attribute mapper + header validation; A5 fetch_vertices on RESTPP/mock tiers |
| app/graph/tiered_client.py | MODIFIED | A1 shared mapper in pyTigerGraph/MCP tiers; A5 fetch_vertices + dispatch |
| app/graph/foundation_store.py | MODIFIED | A3 BOM-tolerant CSV read; A7 repo-root path resolution |
| app/graph/mock/mock_graph_data_service.py | MODIFIED | A3 BOM-tolerant CSV read |
| app/ingestion/ingestion_service.py | MODIFIED | A4 checkpoint honesty (tallies/hashes only after confirmed flush); A6 guarded deletes; A8 clear_checkpoints; A2/A3 csv-aware counting |
| app/ingestion/tigergraph_upsert.py | MODIFIED | A4 fallback-tier write fails the batch; A7 manifest path |
| app/ingestion/validation_engine.py | MODIFIED | A1 pre-flight exact header validation |
| app/ingestion/entity_registry.py | MODIFIED | A1 config carries manifest column mapping; A7 manifest path |
| app/ingestion/graph_validation.py | **NEW** | A5 graph-truth validation (VALIDATED/EMPTY_ATTRS/MISMATCH/NOT_LOADED/UNVERIFIABLE) |
| app/models/ingestion.py | MODIFIED | A1 columns field on IngestionEntityConfig |
| app/api/routers/ingestion.py | MODIFIED | A5 GET /ingestion/validation; A8 POST /ingestion/clear-checkpoints; B3 run-all batch_size; B4 GET /ingestion/errors |
| app/ingestion/run_all.py | MODIFIED | B1 current_entity_index + per-entity batch_size; B3 override; B5 end message |
| app/ingestion/remediation.py | **NEW** | B4 remediation hints for persisted errors |
| app/ingestion/checkpoint_repository.py | MODIFIED | B4 list_errors() |
| app/api/middleware/error_handlers.py | MODIFIED | A6 CORS-safe catch-all (500s now carry CORS headers + real message) |
| app/api/main.py | MODIFIED | A7 startup logging of resolved absolute paths |
| app/config/settings.py | MODIFIED | A7 APP_ROOT anchoring, resolved_* properties, .env at repo root |
| app/feature_store/sqlite_manager.py | MODIFIED | A7 SQLite DB path anchored at repo root |
| app/services/environment_health_service.py | MODIFIED | A7 resolved_paths in /env-health |
| app/shared/logging.py | MODIFIED | A7 log dir anchored at repo root |
| app/v2/dataset/builder.py | MODIFIED | A3 LF lineterminator; csv-aware count in preserve_or_create |
| app/v2/commentary/generation_workflow.py | MODIFIED | A3 LF + BOM-tolerant CSV IO; A7 data dir resolution |

### Frontend (work-stream B)
| File | Change | Why |
|---|---|---|
| frontend/components/ingestion/data-ingestion-workspace.tsx | MODIFIED | B rebuild: validation column, run-all live progress, error expansion, remediation summary, batch override, clear-checkpoints, delete report |
| frontend/lib/api/ingestion.ts | MODIFIED | validation/errors/clear-checkpoints APIs; batch_size + current_entity_index types |

### Backend / frontend (work-stream D)
| File | Change | Why |
|---|---|---|
| app/v2/drivers/attribution.py | MODIFIED | D1 BASELINE_LIMITED driver; NEW/LOST skipped on baseline transition |
| app/v2/dataset/builder.py | MODIFIED | D1 baseline month from data; BASELINE_LIMITED cause seed row |
| app/agents/nodes/commentary_agent.py | MODIFIED | D2 prompt + fallback guard (never narrate as business events) |
| app/agents/nodes/explainability_agent.py | MODIFIED | D2 evidence panels (meaning/step/waterfall/why) for BASELINE_LIMITED |
| frontend/components/ai-insights/commentary-cards.tsx | MODIFIED | D2 first-transition baseline note |
| frontend/components/evidence/evidence-modal.tsx | MODIFIED | D2 waterfall cause order |
| frontend/components/patterns/revenue-driver-glossary.tsx | MODIFIED | D2 glossary row |
| data/sample/** (regenerated) | MODIFIED | D3 sample exercises BASELINE_LIMITED + LOST_ACCOUNT; commentary v11-v13 added (additive) |
| scripts/generate_sample_data.py | MODIFIED | D3 Apr-only account story; lost-account story moved to May->Jun |
| scripts/verify_end_to_end.py | MODIFIED | D3 cause check 15 -> 16 (asserting the new cause model, not old broken behaviour) |

### Scripts / schema / docs
| File | Change | Why |
|---|---|---|
| docs/tigergraph_foundation/tigergraph/schema/90_drop_all.gsql | **NEW** | A8 full drop in dependency order |
| scripts/make_ingestion_fixtures.py | **NEW** | A9a fixture generator (fixtures themselves are gitignored) |
| scripts/verify_ingestion_fixes.py | **NEW** | A9a verification gate (25 checks, local tier) |
| scripts/make_test_raw_extracts.py | MODIFIED | A3 LF lineterminator |
| docs/ROUND5_ACCEPTANCE.md | **NEW** | A9b operator acceptance checklist |
| RUNBOOK.md | MODIFIED | A8 Step 10 clean-slate reset; Step 9 URLs corrected to /ingestion/* |
| .gitignore | MODIFIED | data/fixtures/ ignored |
| PROGRESS.md | MODIFIED | round 5 task tracking (informational) |
| ROUND5_STARTER_PROMPT.md | NEW | session record only — no need to copy |
| docs/ROUND5_CHANGED_FILES.md | NEW | this manifest |

## DO NOT COPY — operator-local files
These commonly differ in the client environment; copying them would overwrite local settings.
| File | Reason |
|---|---|
| .env | operator has local TG credentials, SQLITE_DB_PATH, DATA_SET |
| data/real/** | client data, gitignored |
| data/fixtures/** | local test fixtures, gitignored — regenerate with scripts/make_ingestion_fixtures.py |
| any *.db / *.sqlite | local runtime state |
| logs/** | local runtime logs |

## ⚠ REVIEW BEFORE COPYING — may conflict with operator edits
| File | What round 5 changed | Operator may have changed |
|---|---|---|
| .env.example | (nothing yet in round 5 — will be flagged here if a later work-stream touches it) | local values documented from round 4 |
| docs/data/source_catalog.json | NOT changed in round 5 | date window / table names |
| RUNBOOK.md | added Step 10 (clean-slate reset); corrected Step 9 curl URLs from /api/v2-foundation/ingestion/* to /ingestion/* | operator notes; if locally annotated, merge the new Step 10 rather than overwrite |

## New directories to create
- data/fixtures/  (gitignored — do NOT copy contents; regenerate locally if wanted)

## Deletions / renames
- (none in work-stream A)

## Post-copy steps
1. Restart the backend and confirm the startup log line `Resolved paths:` shows the
   expected absolute SQLite DB / data dir / manifest (A7).
2. `python scripts/make_ingestion_fixtures.py && python scripts/verify_ingestion_fixes.py`
   → OVERALL: PASS (proves the copy is complete on the local tier).
3. Follow `docs/ROUND5_ACCEPTANCE.md` against live TigerGraph.
