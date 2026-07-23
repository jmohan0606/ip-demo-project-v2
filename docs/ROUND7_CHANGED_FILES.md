# Round 7 — Changed Files

Generated: 2026-07-23   Base commit: 1fa844a (round 7 spec)   Head: Ask iPerform complete — `git diff --name-status 1fa844a..HEAD` is the authority

Derived from `git diff --name-status 1fa844a..HEAD`. The operator copies files
from this list literally into the client environment; nothing outside it
changed. Operator-local files (`.env`, anything under `data/real/`,
`frontend/.env.local`) are NOT in this round's diff and must not be
overwritten. `PROGRESS.md`, `BUILD_REPORT.md` and `docs/ROUND7_*.md` are
build-log artifacts — copy or skip at the operator's preference.

## Copy these to the client environment

### Work-stream Z-schema — conversation persistence (⚠ live schema change)

| File | Change | Why |
|---|---|---|
| docs/tigergraph_foundation/tigergraph/schema/01_vertices.gsql | MODIFIED | Z-A1/A12: phx_dm_v2_conversation + phx_dm_v2_message (incl. guardrail_status/guardrail_json) ⚠ re-run DDL + 03_create_graph on the live box |
| docs/tigergraph_foundation/tigergraph/schema/02_edges.gsql | MODIFIED | Z-A1: message_in_conversation + conversation_for_advisor ⚠ live schema change |
| docs/tigergraph_foundation/tigergraph/schema/03_create_graph.gsql | MODIFIED | new types added to the graph statement ⚠ live schema change |
| docs/tigergraph_foundation/tigergraph/schema/90_drop_all.gsql | MODIFIED | regenerated: 22 vertices / 32 edges / 21 queries ⚠ NEEDS-LIVE-VERIFICATION |
| docs/tigergraph_foundation/tigergraph/schema/schema_catalog.json | MODIFIED | regenerated from DDL (typed attribute catalog drives upserts) |
| docs/tigergraph_foundation/tigergraph/loading/jobs/load_v2_all.gsql | MODIFIED | regenerated: loading jobs for the 4 new CSVs |
| docs/tigergraph_foundation/data/manifest.json | MODIFIED | ⚠ CONFLICT RISK: on the client this file is rewritten by scripts/build_real_data.py with real counts — re-run that script after copying rather than hand-merging |
| docs/tigergraph_foundation/tigergraph/queries/GQ-020_get_conversations.gsql | **NEW** | Z-A6 rehydration list ⚠ NEEDS-LIVE-INSTALL (datetime_add window — verify syntax) |
| docs/tigergraph_foundation/tigergraph/queries/GQ-021_get_conversation_messages.gsql | **NEW** | Z-A6 transcript ⚠ NEEDS-LIVE-INSTALL |
| docs/tigergraph_foundation/tigergraph/queries/query_catalog.json | MODIFIED | 21 queries (GQ-020/021 entries) |
| docs/tigergraph_foundation/tigergraph/queries/install_all_queries.gsql | MODIFIED | +2 install lines |
| docs/tigergraph_foundation/tigergraph/queries/tests/query_cases.json | MODIFIED | cases for the 2 new queries |

### Work-stream Z-backend — assistant engine

| File | Change | Why |
|---|---|---|
| app/v2/assistant/__init__.py | **NEW** | package |
| app/v2/assistant/guardrail_gate.py | **NEW** | Z-A10/A11/A12: input/output gate over app/guardrails; PII redaction before persistence; category+severity-only findings; ACCOUNT-number exemption (recorded decision) |
| app/v2/assistant/router.py | **NEW** | Z-A3: deterministic rule table for all 10 A3 intents + entity extraction vs loaded data |
| app/v2/assistant/llm_fallback.py | **NEW** | Z-A4: constrained {query,params} selection, validated against the catalog |
| app/v2/assistant/context.py | **NEW** | Z-A5: question > pinned > inherited > screen > default; chip label |
| app/v2/assistant/providers.py | **NEW** | Z-A2: ASSISTANT_LLM_MODE chain (cdao primary in client env); logged fallback |
| app/v2/assistant/answers.py | **NEW** | per-intent builders — arrangement of stored figures only; figures_json with source query + provenance |
| app/v2/assistant/service.py | **NEW** | A9 order of operations; narration under the no-invented-figures guardrail; NO_DATA/OUT_OF_SCOPE/BLOCKED; advice pattern |
| app/v2/assistant/store.py | **NEW** | Z-A1: tiered persistence (graph system of record, CSV local fallback), reads via GQ-020/021 |
| app/api/routers/v2.py | MODIFIED | /api/v2/assistant/{ask, conversations, conversations/{id}, config} |
| app/graph/queries/common.py | MODIFIED | CONVERSATION/MESSAGE constants + V2_VERTEX_TYPES |
| app/graph/queries/v2.py | MODIFIED | local-tier get_conversations / get_conversation_messages |
| app/guardrails/service.py | MODIFIED | neutral_refusal() (A9 wording; safe_refusal untouched for V1 surfaces) |
| app/config/settings.py | MODIFIED | ASSISTANT_LLM_MODE / ASSISTANT_LLM_FALLBACK_MODES / ASSISTANT_HISTORY_DAYS |
| app/v2/dataset/builder.py | MODIFIED | chat CSVs as workflow artifacts (preserved on regeneration) + manifest entries |
| .env.example | MODIFIED | ASSISTANT_* keys ⚠ merge into the client's .env by hand — do not overwrite it |

### Work-stream Z-ui — overlay + full page

| File | Change | Why |
|---|---|---|
| frontend/components/assistant/assistant-context.tsx | **NEW** | Z-B1: shell-level conversation state; persists across navigation; reload rehydration |
| frontend/components/assistant/assistant-panel.tsx | **NEW** | Z-B3: shared conversation surface (both presentations); AI chip on wording only; figures unmarked; Ran: trail; GUARDRAIL chip |
| frontend/components/assistant/assistant-overlay.tsx | **NEW** | Z-B1: 420px overlay, History dropdown, expand, collapse-to-button |
| frontend/app/(dashboard)/ask/page.tsx | **NEW** | Z-B2: full-page view, grouped conversation rail — same component |
| frontend/components/layout/v2-shell.tsx | MODIFIED | ⚠ CONFLICT RISK (touched most rounds): AssistantProvider mount + overlay + "Ask iPerform" tab |
| frontend/lib/api/v2.ts | MODIFIED | ⚠ CONFLICT RISK (touched most rounds): assistant types + fetchers appended |

### Work-stream Z-verify — proofs and data

| File | Change | Why |
|---|---|---|
| scripts/verify_assistant.py | **NEW** | Z-C1: checks 1-6 + 8 (84/84 PASS); restores chat CSVs after the run |
| scripts/verify_assistant_ui.mjs | **NEW** | Z-C1 check 7: headless walk, 7/7, zero console errors (needs both servers) |
| data/sample/vertices/phx_dm_v2_conversation.csv | **NEW** | header-only workflow artifact |
| data/sample/vertices/phx_dm_v2_message.csv | **NEW** | header-only workflow artifact |
| data/sample/edges/phx_dm_v2_message_in_conversation.csv | **NEW** | header-only workflow artifact |
| data/sample/edges/phx_dm_v2_conversation_for_advisor.csv | **NEW** | header-only workflow artifact |
| docs/ROUND7_ACCEPTANCE.md | **NEW** | operator-only acceptance steps |
| docs/ROUND7_CHANGED_FILES.md | **NEW** | this file |
| PROGRESS.md / BUILD_REPORT.md | MODIFIED | build log |

## Conflict-risk summary

Highest-risk files if the client tree has drifted: `frontend/lib/api/v2.ts`,
`frontend/components/layout/v2-shell.tsx` (both modified nearly every round —
diff before copying), `docs/tigergraph_foundation/data/manifest.json`
(regenerate on the client with `build_real_data.py` instead of copying), and
`.env.example` (merge keys, never overwrite the live `.env`).
