# ROUND 12 CHANGED FILES — per-role LLM config + auto-fallback

Git-derived: `git diff --name-status eb9b6a2..HEAD` (round-11 wrap → round-12 wrap).
Operator-local material (data/real/, prompts/, qa_screenshots/, .env) is untouched this
round and excluded by construction. LLM plumbing only — no attribution, taxonomy,
eligibility or computed-figure file changed; reconciliation stays $0.00.

**Conflict-risk flag (⚠):** files the operator may have edited locally (settings,
.env template, shared UI shell files from earlier rounds). Take the repo version and
re-apply local edits, or diff before overwriting.

| File | Status | What changed | Conflict risk |
|------|--------|--------------|---------------|
| `app/llm/roles.py` | A | NEW — shared role→effective-config resolution (`resolve_role_config`), `RoleLLM` single-retry auto-fallback wrapper, served-path recording | — |
| `app/config/settings.py` | M | +10 optional keys: `WRITER_CLIENT_MODE/MODEL/DEPLOYMENT/API_VERSION`, `JUDGE_CLIENT_MODE/DEPLOYMENT/API_VERSION`, `ASSISTANT_MODEL/DEPLOYMENT/API_VERSION` (existing `JUDGE_MODEL`/`JUDGE_ENABLED`/`ASSISTANT_LLM_MODE`/`ASSISTANT_LLM_FALLBACK_MODES` reused, not duplicated) | ⚠ operator may hold local settings edits |
| `.env.example` | M | commented examples for every new key + the deployment-vs-model-vs-api_version explanation | ⚠ operator's real .env is separate; template may be locally annotated |
| `app/llm/client.py` | M | `build_llm_client` + `RealLLMClient` + `CdaoOpenAILLMClient` accept `deployment_override`/`api_version_override`; guarded cdao import unchanged | ⚠ touched in R9/R10 too |
| `app/agents/nodes/commentary_agent.py` | M | writer obtains its client via `build_role_llm("writer")` (falls to the app singleton when unconfigured); `llm_path` metadata on commentary | ⚠ prompts/fallbacks edited across rounds |
| `app/v2/commentary/judge.py` | M | `get_judge_llm` uses the shared helper when any new judge key is set (JUDGE_MODEL alone keeps the exact R9 path); mock-fallback = honest UNAVAILABLE; `llm_path` on evaluations | — |
| `app/v2/commentary/generation_workflow.py` | M | version-row `model` label reflects the writer's effective config (metadata only) | ⚠ touched in R11 (async/per-advisor) |
| `app/v2/assistant/providers.py` | M | primary chain link carries the assistant's role config; R12 default-agent-LLM retry as the FINAL link after the unchanged R7 chain; `served_path` on every result | — |
| `app/v2/assistant/service.py` | M | served path threaded into the turn's `llm_provider` label (only when configured or fallen back — unconfigured labels unchanged) | — |
| `app/services/llm_connectivity.py` | M | Env Health rows show each role's EFFECTIVE mode/model/deployment/api_version + reachability of that config + "will fall back" note; no secrets | — |
| `frontend/lib/api/env-health.ts` | M | `LlmConnectivityRow` + `deployment`/`api_version`/`fallback` fields | — |
| `frontend/components/env-health/env-health-workspace.tsx` | M | LLM connectivity table: Deployment + api_version columns, will-fall-back note | ⚠ shared screen file across rounds |
| `scripts/verify_role_llm.py` | A | NEW — 32 fixture checks (regression / role_config / fallback / honest states / Env Health, no secrets) | — |
| `docs/ROUND12_ACCEPTANCE.md` | A | operator real-cdao checks + how-to-configure-each-role table | — |
| `docs/ROUND12_CHANGED_FILES.md` | A | this file | — |
| `PROGRESS.md` | M | Q-task tracking | — |
| `ROUND12_STARTER_PROMPT.md` | A | round input (committed for the record) | — |
| `BUILD_REPORT.md` | M | §18 Round 12 (+ Q-F defect-fix note) | — |

**Post-round defect fix Q-F** (glossary display_order sorted as STRING — commit 8d883d6):

| File | Status | What changed | Conflict risk |
|------|--------|--------------|---------------|
| `app/v2/revenue/service.py` | M | `driver_causes()` re-imposes numeric display_order on every serving tier (`_display_order_key`: missing/invalid last, name tiebreak) | — |
| `app/graph/queries/v2.py` | M | `_int` coerces via float so numeric TEXT sorts numerically | ⚠ local-tier impls edited across rounds |
| `frontend/lib/v2/driver-causes.tsx` | M | glossary sort key is an explicit `Number(display_order)` | — |
| `docs/tigergraph_foundation/tigergraph/queries/GQ-004_get_driver_causes.gsql` | M | header note: STRING-typed pre-R8 live install sorts lexicographically → reinstall from current DDL (comment only, query unchanged) | — |
| `scripts/verify_glossary_order.py` | A | NEW — 7 checks incl. simulated STRING-typed tier-1 result restored to numeric 1..19 | — |
