# CLIENT ENV SYNC — CONSOLIDATED CHANGED FILES, ROUNDS 9–11

One deduplicated list of every file changed across rounds 9, 10 and 11,
**derived from git** (`git diff --name-status 2f1a13e..HEAD`, where `2f1a13e`
is the round-9 spec commit and `HEAD` = `e9b2ae6`, the round-11 wrap), and
cross-checked against the three per-round documents:

- `docs/ROUND9_CHANGED_FILES.md`  (span `2f1a13e..c1b0f72`)
- `docs/ROUND10_CHANGED_FILES.md` (span `c1b0f72..ddf1172`)
- `docs/ROUND11_CHANGED_FILES.md` (span `ddf1172..e9b2ae6`)

**127 files: 21 added, 106 modified, 0 deleted/renamed.** "Final status" is
the status over the whole 9→11 span (a file added in R10 and edited in R11 is
one "Added" row). "Rounds" is computed per round span from git, with the two
round-opening spec commits attributed to the round they open.

**Flags are carried forward verbatim in meaning** from the three round docs:
**CONFLICT-RISK** = the operator may hold local edits — diff before
overwriting (the rounds that flagged it are in parentheses); NEEDS LIVE
REINSTALL = the GSQL must be reinstalled on live TigerGraph; per-file operator
notes are repeated where a round doc carried one.

## Cross-check: git-derived list vs. the union of the three round docs

The assertion below was produced by machine comparison (scripted, not from
memory): every git path was tested for coverage by the three docs' explicit
paths and their stated glob/shorthand notations, and every path-like mention
in the docs was tested for existence in the git list.

**Result: the two lists MATCH, with exactly two exceptions, both in one
direction (changed in git but listed in no round doc):**

| File | Why it was missed | Disposition |
|---|---|---|
| `FIX_SPEC_R10.md` | the operator-authored round-10 spec, committed by the round-opening commit `c1b0f72`; ROUND10_CHANGED_FILES listed the starter prompt but not the spec itself | documented here; content is the operator's own input — no sync action |
| `FIX_SPEC_R11.md` | same pattern, commit `ddf1172` | documented here; no sync action |

No file is documented in a round doc but absent from git. Apparent one-way
mentions all resolved as **notation, not mismatches**:

- Doc globs/shorthand expand to real git paths: `data/sample/**`,
  `phx_dm_v2_commentary*.csv` (+ the R9 bare CSV names `phx_dm_v2_evidence.csv`,
  `phx_dm_v2_evidence_for_driver.csv`, `phx_dm_v2_evaluation_of_commentary.csv`),
  `GQ-009/010/018/019*.gsql` (four files), and the bare `build_real_data.py`
  (= `scripts/build_real_data.py`).
- Deliberately excluded **operator-local** material (never committed; the
  operator's copies are authoritative): `data/real/**`, `prompts/**`, `.env`,
  gitignored `docs/qa_screenshots/` and `data/fixtures/`
  (`scripts/make_ingestion_fixtures.py` regenerates the latter and is
  mentioned in R9 only as the tool, unchanged in rounds 9–11).

## Consolidated file list (127 files, deduplicated, final status over 9→11)

### Round inputs & bookkeeping (15 files)

| File | Final status | Rounds | Flags |
|---|---|---|---|
| `BUILD_REPORT.md` | Modified | R9+R10+R11 | — |
| `CLAUDE.md` | Modified | R11 | **CONFLICT-RISK** (R11) |
| `FIX_SPEC_R10.md` | Added | R10 | — |
| `FIX_SPEC_R11.md` | Added | R11 | — |
| `PROGRESS.md` | Modified | R9+R10+R11 | — |
| `ROUND10_STARTER_PROMPT.md` | Added | R10 | — |
| `ROUND11_STARTER_PROMPT.md` | Added | R11 | — |
| `ROUND9_STARTER_PROMPT.md` | Added | R9 | — |
| `docs/ROUND10_ACCEPTANCE.md` | Added | R10 | — |
| `docs/ROUND10_CHANGED_FILES.md` | Added | R10 | — |
| `docs/ROUND11_ACCEPTANCE.md` | Added | R11 | — |
| `docs/ROUND11_CHANGED_FILES.md` | Added | R11 | — |
| `docs/ROUND9_ACCEPTANCE.md` | Added | R9 | — |
| `docs/ROUND9_CHANGED_FILES.md` | Added | R9 | — |
| `docs/SOLUTION_GUIDE.md` | Modified | R11 | **CONFLICT-RISK** (R11) |

### Backend — app/ (22 files)

| File | Final status | Rounds | Flags |
|---|---|---|---|
| `.env.example` | Modified | R9 | **CONFLICT-RISK** (R9); operator `.env` needs `COMMENTARY_MAX_ATTEMPTS` (optional) + `JUDGE_MODEL` review (R9 note) |
| `app/agents/nodes/commentary_agent.py` | Modified | R9 | — |
| `app/agents/nodes/explainability_agent.py` | Modified | R10 | — |
| `app/agents/nodes/supervisor_agent.py` | Modified | R9 | — |
| `app/api/routers/v2.py` | Modified | R11 | **CONFLICT-RISK** (R11) |
| `app/config/settings.py` | Modified | R9 | **CONFLICT-RISK** (R9) |
| `app/graph/queries/v2.py` | Modified | R9+R11 | **CONFLICT-RISK** (R11) |
| `app/llm/client.py` | Modified | R9 | — |
| `app/services/environment_health_service.py` | Modified | R10 | — |
| `app/services/llm_connectivity.py` | Added | R10 | — |
| `app/v2/anomalies/detection.py` | Modified | R11 | — |
| `app/v2/anomalies/service.py` | Modified | R11 | — |
| `app/v2/assistant/answers.py` | Modified | R9 | — |
| `app/v2/assistant/context.py` | Modified | R9 | — |
| `app/v2/assistant/service.py` | Modified | R9+R11 | — |
| `app/v2/assistant/store.py` | Modified | R9 | — |
| `app/v2/commentary/generation_workflow.py` | Modified | R9+R11 | **CONFLICT-RISK** (R9+R11) |
| `app/v2/commentary/judge.py` | Modified | R9 | — |
| `app/v2/dataset/builder.py` | Modified | R9+R10+R11 | **CONFLICT-RISK** (R9+R10+R11) |
| `app/v2/drivers/attribution.py` | Modified | R9+R10 | **CONFLICT-RISK** (R9+R10); operator kept edited copies under `prompts/` — diff before merging (R9 note) |
| `app/v2/revenue/eligibility.py` | Modified | R10 | — |
| `app/v2/revenue/taxonomy.py` | Added | R10+R11 | **CONFLICT-RISK** (R11) |

### Graph artifacts (schema, loading, queries) (10 files)

| File | Final status | Rounds | Flags |
|---|---|---|---|
| `docs/tigergraph_foundation/tigergraph/loading/jobs/load_v2_all.gsql` | Modified | R9+R11 | **CONFLICT-RISK** (R9) |
| `docs/tigergraph_foundation/tigergraph/queries/GQ-009_get_commentary.gsql` | Modified | R11 | NEEDS LIVE REINSTALL (R11) |
| `docs/tigergraph_foundation/tigergraph/queries/GQ-010_get_commentary_versions.gsql` | Modified | R11 | NEEDS LIVE REINSTALL (R11) |
| `docs/tigergraph_foundation/tigergraph/queries/GQ-018_get_anomalies.gsql` | Modified | R11 | NEEDS LIVE REINSTALL (R11) |
| `docs/tigergraph_foundation/tigergraph/queries/GQ-019_get_anomaly_scans.gsql` | Modified | R11 | NEEDS LIVE REINSTALL (R11) |
| `docs/tigergraph_foundation/tigergraph/queries/GQ-020_get_conversations.gsql` | Modified | R9 | NEEDS LIVE REINSTALL (R9) |
| `docs/tigergraph_foundation/tigergraph/queries/query_catalog.json` | Modified | R9+R11 | **CONFLICT-RISK** (R9+R11) |
| `docs/tigergraph_foundation/tigergraph/queries/tests/query_cases.json` | Modified | R11 | — |
| `docs/tigergraph_foundation/tigergraph/schema/01_vertices.gsql` | Modified | R9+R11 | **CONFLICT-RISK** (R11); schema attribute additions need the live drop/recreate or alter path (R9 conversation vertex; R11 advisor_sid x2) |
| `docs/tigergraph_foundation/tigergraph/schema/schema_catalog.json` | Modified | R9+R11 | — |

### Ingestion manifest (1 files)

| File | Final status | Rounds | Flags |
|---|---|---|---|
| `docs/tigergraph_foundation/data/manifest.json` | Modified | R9+R10+R11 | **CONFLICT-RISK** (R9+R10+R11); rewritten by `build_real_data.py` on the client machine — take the repo version, then rebuild (R9/R11 note) |

### Frontend (14 files)

| File | Final status | Rounds | Flags |
|---|---|---|---|
| `frontend/app/(dashboard)/ai-insights/page.tsx` | Modified | R11 | **CONFLICT-RISK** (R11) |
| `frontend/app/(dashboard)/anomalies/page.tsx` | Modified | R11 | — |
| `frontend/components/ai-insights/commentary-cards.tsx` | Modified | R9+R11 | **CONFLICT-RISK** (R11) |
| `frontend/components/ai-insights/export-data.ts` | Modified | R9 | — |
| `frontend/components/ai-insights/monthly-walk-table.tsx` | Modified | R9 | — |
| `frontend/components/assistant/assistant-context.tsx` | Modified | R9 | — |
| `frontend/components/assistant/assistant-panel.tsx` | Modified | R9 | — |
| `frontend/components/env-health/env-health-workspace.tsx` | Modified | R10 | **CONFLICT-RISK** (R10) |
| `frontend/components/evidence/evidence-modal.tsx` | Modified | R9+R10 | **CONFLICT-RISK** (R9+R10) |
| `frontend/components/layout/v2-shell.tsx` | Modified | R9 | **CONFLICT-RISK** (R9) |
| `frontend/components/patterns/job-progress.tsx` | Added | R11 | — |
| `frontend/lib/api/env-health.ts` | Modified | R10 | — |
| `frontend/lib/api/v2.ts` | Modified | R9+R11 | **CONFLICT-RISK** (R9+R11) |
| `frontend/lib/v2/driver-causes.tsx` | Modified | R9 | — |

### Scripts (build + verification) (14 files)

| File | Final status | Rounds | Flags |
|---|---|---|---|
| `scripts/build_real_data.py` | Modified | R10+R11 | **CONFLICT-RISK** (R10) |
| `scripts/generate_sample_data.py` | Modified | R10+R11 | **CONFLICT-RISK** (R10+R11) |
| `scripts/generate_schema_artifacts.py` | Modified | R9 | — |
| `scripts/verify_anomalies.py` | Modified | R11 | — |
| `scripts/verify_assistant.py` | Modified | R9+R10+R11 | — |
| `scripts/verify_attribution.py` | Modified | R9+R11 | — |
| `scripts/verify_clawback_scope.py` | Added | R10 | — |
| `scripts/verify_commentary_retry.py` | Added | R9 | — |
| `scripts/verify_eligibility.py` | Added | R10 | — |
| `scripts/verify_end_to_end.py` | Modified | R9+R10+R11 | — |
| `scripts/verify_judge.py` | Added | R9+R11 | — |
| `scripts/verify_new_drivers.py` | Added | R10 | — |
| `scripts/verify_per_advisor.py` | Added | R11 | — |
| `scripts/verify_taxonomy.py` | Added | R10+R11 | — |

### Sample data set (test asset; regenerated) (51 files)

| File | Final status | Rounds | Flags |
|---|---|---|---|
| `data/sample/edges/phx_dm_v2_anomaly_cites_driver.csv` | Modified | R11 | — |
| `data/sample/edges/phx_dm_v2_anomaly_for_advisor.csv` | Modified | R11 | — |
| `data/sample/edges/phx_dm_v2_anomaly_in_scan.csv` | Modified | R11 | — |
| `data/sample/edges/phx_dm_v2_balance_for_account.csv` | Modified | R11 | — |
| `data/sample/edges/phx_dm_v2_balance_in_month.csv` | Modified | R11 | — |
| `data/sample/edges/phx_dm_v2_change_for_advisor.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_change_for_group.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_change_from_month.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_change_to_month.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_commentary_cites_driver.csv` | Modified | R9+R10+R11 | — |
| `data/sample/edges/phx_dm_v2_commentary_for_advisor.csv` | Modified | R9+R10+R11 | — |
| `data/sample/edges/phx_dm_v2_commentary_from_month.csv` | Modified | R9+R10+R11 | — |
| `data/sample/edges/phx_dm_v2_commentary_in_version.csv` | Modified | R9+R10+R11 | — |
| `data/sample/edges/phx_dm_v2_commentary_to_month.csv` | Modified | R9+R10+R11 | — |
| `data/sample/edges/phx_dm_v2_conversation_for_advisor.csv` | Modified | R11 | — |
| `data/sample/edges/phx_dm_v2_driver_for_group.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_driver_has_cause.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_driver_of_change.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_evaluation_of_commentary.csv` | Modified | R9+R10+R11 | — |
| `data/sample/edges/phx_dm_v2_evidence_for_driver.csv` | Modified | R9+R10+R11 | — |
| `data/sample/edges/phx_dm_v2_group_in_line.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_line_in_class.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_message_in_conversation.csv` | Modified | R11 | — |
| `data/sample/edges/phx_dm_v2_mpr_for_advisor.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_mpr_for_group.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_mpr_in_month.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_product_in_group.csv` | Modified | R10 | — |
| `data/sample/edges/phx_dm_v2_txn_for_account.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_txn_for_advisor.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_txn_for_product.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_txn_has_reason.csv` | Modified | R10+R11 | — |
| `data/sample/edges/phx_dm_v2_txn_in_month.csv` | Modified | R10+R11 | — |
| `data/sample/vertices/phx_dm_v2_account_month_balance.csv` | Modified | R11 | — |
| `data/sample/vertices/phx_dm_v2_anomaly.csv` | Modified | R11 | — |
| `data/sample/vertices/phx_dm_v2_anomaly_scan.csv` | Modified | R11 | — |
| `data/sample/vertices/phx_dm_v2_commentary.csv` | Modified | R9+R10+R11 | — |
| `data/sample/vertices/phx_dm_v2_commentary_evaluation.csv` | Modified | R9+R10+R11 | — |
| `data/sample/vertices/phx_dm_v2_commentary_version.csv` | Modified | R9+R10+R11 | — |
| `data/sample/vertices/phx_dm_v2_conversation.csv` | Modified | R9+R11 | — |
| `data/sample/vertices/phx_dm_v2_driver_cause.csv` | Modified | R10 | — |
| `data/sample/vertices/phx_dm_v2_evidence.csv` | Modified | R9+R10+R11 | — |
| `data/sample/vertices/phx_dm_v2_message.csv` | Modified | R11 | — |
| `data/sample/vertices/phx_dm_v2_month.csv` | Modified | R11 | — |
| `data/sample/vertices/phx_dm_v2_monthly_product_revenue.csv` | Modified | R10+R11 | — |
| `data/sample/vertices/phx_dm_v2_product.csv` | Modified | R10 | — |
| `data/sample/vertices/phx_dm_v2_product_group.csv` | Modified | R10+R11 | — |
| `data/sample/vertices/phx_dm_v2_product_line.csv` | Modified | R10+R11 | — |
| `data/sample/vertices/phx_dm_v2_reason_code.csv` | Modified | R10 | — |
| `data/sample/vertices/phx_dm_v2_revenue_change.csv` | Modified | R10+R11 | — |
| `data/sample/vertices/phx_dm_v2_revenue_driver.csv` | Modified | R9+R10+R11 | — |
| `data/sample/vertices/phx_dm_v2_revenue_transaction.csv` | Modified | R10+R11 | — |
## Sync order reminder (from the round acceptance docs)

1. Take the repo tree, diffing every **CONFLICT-RISK** file against local
   edits first (especially `app/v2/drivers/attribution.py` — R9 noted the
   operator kept edited copies under `prompts/`).
2. Apply schema changes (`01_vertices.gsql`: R9 conversation vertex +
   advisor_sid; R11 `advisor_sid` on `phx_dm_v2_commentary_version` and
   `phx_dm_v2_anomaly_scan`), then reinstall the five flagged queries
   (GQ-009, GQ-010, GQ-018, GQ-019, GQ-020).
3. Let `build_real_data.py` regenerate `manifest.json` and `data/real/**`
   locally — the committed manifest is sample-scoped.
4. Review `.env` against `.env.example` (`COMMENTARY_MAX_ATTEMPTS`,
   `JUDGE_MODEL`).

---

## Addendum — Round 12 + post-round fixes (files changed AFTER the R9–R11 span)

Git-derived from `e9b2ae6..99b7914` (round-11 wrap → round-12 wrap + Q-F/Q-G
fixes), deduplicated the same way as the main list. Round 12 is **LLM plumbing
only** (per-role writer/judge/assistant config + auto-fallback — no computed
figure, reconciliation unchanged at $0.00); Q-F fixes the R8/R9 glossary
display_order string-sort defect; Q-G is a cosmetic launcher change. Flags
carry the same meaning as above. The chat sample CSVs are NOT in this list:
verify-run residue swept into commit 8d883d6 was reverted to the R11 state.

| File | Status | Round / task | Flags & notes |
|---|---|---|---|
| `app/llm/roles.py` | Added | R12 Q-A/Q-C | shared role→config resolution + RoleLLM auto-fallback |
| `app/config/settings.py` | Modified | R12 Q-A | +10 per-role keys — **CONFLICT-RISK** (R9/R10/R11/R12) |
| `.env.example` | Modified | R12 Q-A/Q-D2 | per-role key examples; deployment-vs-model-vs-api_version note — **CONFLICT-RISK** |
| `app/llm/client.py` | Modified | R12 Q-B | builder + Azure-shaped adapters take deployment/api_version overrides — **CONFLICT-RISK** (R9/R12) |
| `app/agents/nodes/commentary_agent.py` | Modified | R12 Q-C | writer via role helper; `llm_path` metadata — **CONFLICT-RISK** (prompts edited across rounds) |
| `app/v2/commentary/judge.py` | Modified | R12 Q-C | judge role config + fallback; JUDGE_MODEL-alone keeps R9 path |
| `app/v2/commentary/generation_workflow.py` | Modified | R12 Q-C | version-row model label from writer's effective config — **CONFLICT-RISK** (R11) |
| `app/v2/assistant/providers.py` | Modified | R12 Q-C | R7 chain + R12 final default retry; served_path |
| `app/v2/assistant/service.py` | Modified | R12 Q-C | served path on turn metadata |
| `app/services/llm_connectivity.py` | Modified | R12 Q-D | Env Health per-role effective config + will-fall-back |
| `frontend/lib/api/env-health.ts` | Modified | R12 Q-D | row type: deployment/api_version/fallback |
| `frontend/components/env-health/env-health-workspace.tsx` | Modified | R12 Q-D | LLM table columns — **CONFLICT-RISK** (shared screen file) |
| `scripts/verify_role_llm.py` | Added | R12 Q-C | 32-check fixture suite |
| `app/v2/revenue/service.py` | Modified | Q-F | numeric display_order re-imposed on every serving tier |
| `app/graph/queries/v2.py` | Modified | Q-F | `_int` via float (numeric TEXT sorts numerically) — **CONFLICT-RISK** (local-tier impls) |
| `frontend/lib/v2/driver-causes.tsx` | Modified | Q-F | explicit `Number(display_order)` sort key |
| `docs/tigergraph_foundation/tigergraph/queries/GQ-004_get_driver_causes.gsql` | Modified | Q-F | comment only — **NEEDS LIVE REINSTALL of the SCHEMA if the live graph predates display_order INT** (the query text is unchanged; a STRING-typed install sorts lexicographically) |
| `scripts/verify_glossary_order.py` | Added | Q-F | 7-check ordering suite incl. simulated STRING-typed tier-1 result |
| `frontend/components/assistant/assistant-overlay.tsx` | Modified | Q-G | cosmetic: labelled "Ask iPerform" launcher pill |
| `FIX_SPEC_R12.md` | Added | R12 | operator-authored spec — no sync action |
| `ROUND12_STARTER_PROMPT.md` | Added | R12 | round input, committed for the record — no sync action |
| `docs/ROUND12_ACCEPTANCE.md` | Added | R12 | operator real-cdao checks + per-role config how-to |
| `docs/ROUND12_CHANGED_FILES.md` | Added | R12 | per-round manifest (superset detail of this addendum) |
| `docs/CLIENT_ENV_SYNC_R9_R11.md` | Added | post-R11 | this document |
| `BUILD_REPORT.md` / `PROGRESS.md` | Modified | R12/Q-F/Q-G | build record — take repo version |

**Sync-order additions for this span:** after step 4 above, (5) set any
per-role `WRITER_*` / `JUDGE_*` / `ASSISTANT_*` keys per
`docs/ROUND12_ACCEPTANCE.md` §1 and confirm all three roles in Env Health;
(6) if the live graph was created before `display_order` became INT,
reinstall the schema from the current DDL (GQ-004 header) — the app renders
correctly either way, but the live schema should match the repo.
