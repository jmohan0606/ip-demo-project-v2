# ROUND 9 — CHANGED FILES (git-derived)

Derived from `git diff --name-only 2f1a13e..HEAD` (round-9 spec commit → wrap).
50 files, +5,623 / −227. Commits, in order:

| Commit | Task | Subject |
|---|---|---|
| 78cd968 | — | PROGRESS: N-tasks appended |
| 45e6e4a | N-A | account presence excludes ONE_TIME/ADJUSTMENT rows |
| 350c158 | N-B | account-comparison lists: write contract + read resilience + QUOTE fix |
| 7b77c98 | — | round 9 starter prompt (doc) |
| 1b8f980 | N-C1 | advisor-scoped conversations |
| be8e827 | N-C2 | adjacent seeding, exact labels, multi-month decomposition |
| c3e6864 | N-C3 | blocked turns always visible |
| b2778ba | N-D | commentary prompt v1.2 + retry + deterministic fallback |
| 430ce7a | N-E | judge on standard adapter, honest unavailable |
| 809e0d5 | N-F | glossary display_order |
| (wrap) | N-G | this file, ROUND9_ACCEPTANCE, BUILD_REPORT §, PROGRESS |

**Operator-local files excluded** (never committed; the operator's copies are
authoritative): everything under `data/real/`, `prompts/`,
`docs/qa_screenshots/` (gitignored), `data/fixtures/` (gitignored,
regenerable via `scripts/make_ingestion_fixtures.py`), `.env`.

⚠ = conflict-risk if the operator has local edits (files also touched in
earlier rounds or known to be operator-edited).

## Backend — attribution & data build
- ⚠ `app/v2/drivers/attribution.py` — N-A: presence filter (PRESENCE_EXCLUDED_NATURES),
  recurring-rows-only claims, activity map filter. **The operator previously
  kept edited copies under `prompts/` — diff before merging.**
- ⚠ `app/v2/dataset/builder.py` — N-B `_validate_account_driver_inputs`;
  N-C1 conversation CSV header + `preserve_or_create` additive header migration.
- `app/graph/queries/v2.py` — N-C1: `get_conversations` filters on advisor_sid.

## Backend — assistant (C)
- `app/v2/assistant/service.py` — C1 conversation binding + scope refusal; D non-AI marking pass-through.
- `app/v2/assistant/store.py` — C1 advisor_sid on the row; C3 create-missing-CSV.
- `app/v2/assistant/context.py` — C2 screen-span snap to adjacent.
- `app/v2/assistant/answers.py` — C2 both-months match + `span_decompose`; D `stored_non_ai`.

## Backend — commentary & judge (D, E)
- `app/agents/nodes/commentary_agent.py` — prompt v1.2 sign convention;
  `deterministic_commentary`; latent positive-paren fix in the template.
- `app/agents/nodes/supervisor_agent.py` — bounded retry + fallback install.
- ⚠ `app/v2/commentary/generation_workflow.py` — PUBLISHED_FALLBACK status + summary count.
- `app/v2/commentary/judge.py` — adapter factory routing, JUDGE_MODEL semantics,
  −1.0 UNAVAILABLE sentinel.
- `app/llm/client.py` — `build_llm_client` factory; model_override on cdao/real adapters.
- ⚠ `app/config/settings.py` — `COMMENTARY_MAX_ATTEMPTS`; `JUDGE_MODEL` default now empty.
- ⚠ `.env.example` — the two settings above documented. **The operator's `.env`
  needs `COMMENTARY_MAX_ATTEMPTS` (optional) and a `JUDGE_MODEL` review.**

## Schema & graph artifacts (regenerate/reinstall live)
- `docs/tigergraph_foundation/tigergraph/schema/01_vertices.gsql` — conversation + advisor_sid (only schema change).
- `docs/tigergraph_foundation/tigergraph/schema/schema_catalog.json` — regenerated.
- ⚠ `docs/tigergraph_foundation/tigergraph/loading/jobs/load_v2_all.gsql` — regenerated;
  now `QUOTE="double"` on every LOAD (N-B root cause on the GSQL load path).
- `docs/tigergraph_foundation/tigergraph/queries/GQ-020_get_conversations.gsql` — NEEDS LIVE REINSTALL.
- ⚠ `docs/tigergraph_foundation/tigergraph/queries/query_catalog.json` — GQ-020 entry updated.
- ⚠ `docs/tigergraph_foundation/data/manifest.json` — regenerated (advisor_sid column).
  **On the client machine this file is rewritten by `build_real_data.py` — take the
  repo version, then rebuild.**
- `scripts/generate_schema_artifacts.py` — QUOTE emission.

## Frontend
- ⚠ `frontend/components/evidence/evidence-modal.tsx` — N-B key-path logging +
  legacy fallback; N-E unavailable faithfulness rendering.
- `frontend/components/assistant/assistant-context.tsx` — C1 scoped rail; C2 monthIds
  seeding; C3 local error turns.
- `frontend/components/assistant/assistant-panel.tsx` — C3 chip shows category · severity.
- ⚠ `frontend/components/layout/v2-shell.tsx` — C2 passes the month list to the assistant.
- `frontend/components/ai-insights/commentary-cards.tsx` — D fallback tag (no AI chip).
- `frontend/components/ai-insights/monthly-walk-table.tsx` — D fallback note.
- `frontend/components/ai-insights/export-data.ts` — D fallback prefix in exports.
- ⚠ `frontend/lib/api/v2.ts` — CommentaryRow status union + PUBLISHED_FALLBACK.
- `frontend/lib/v2/driver-causes.tsx` — F robust display_order sort.

## Sample data (regenerated; test asset only)
- `data/sample/vertices/phx_dm_v2_revenue_driver.csv` — N-A/N-B attribution + inputs_json.
- `data/sample/vertices/phx_dm_v2_conversation.csv` — header + advisor_sid.
- `data/sample/vertices/phx_dm_v2_commentary*.csv`, `phx_dm_v2_evidence.csv`,
  `data/sample/edges/phx_dm_v2_commentary_*.csv`, `phx_dm_v2_evaluation_of_commentary.csv`,
  `phx_dm_v2_evidence_for_driver.csv` — commentary v20 (prompt v1.2; 5 PUBLISHED +
  1 PUBLISHED_FALLBACK) appended additively.

## Verification & docs
- `scripts/verify_attribution.py` — R9A + R9B sections; one-time fixture support.
- `scripts/verify_assistant.py` — sections [10]/[11]/[12]; compare fixture updated.
- `scripts/verify_commentary_retry.py` — NEW (D).
- `scripts/verify_judge.py` — NEW (E).
- `scripts/verify_end_to_end.py` — glossary-order checks (F).
- `PROGRESS.md`, `ROUND9_STARTER_PROMPT.md`, `docs/ROUND9_ACCEPTANCE.md`,
  `docs/ROUND9_CHANGED_FILES.md`, `BUILD_REPORT.md` (round-9 section).
