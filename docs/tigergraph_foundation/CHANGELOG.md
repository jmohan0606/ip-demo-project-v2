# Changelog

## v1.2 — bounded presentation-quality data expansion (Section 9.3, 2026-07-05)

- Relabeled display names in place (same ids, same numeric values): 3 divisions, 6 regions,
  12 metro markets, 24 branches with real city/state, 360 households, 720 accounts,
  16 product subcategories, 64 products, 180 CRM opportunity names, 300 CRM activity
  subjects/notes, 72 coaching-session summaries (action-item counts preserved).
- Extended monthly history by 12 OLDER months (2023-08..2024-07 -> 36 periods): +5,036
  revenue transactions, +2,160 monthly product-revenue rows, +720 each monthly AUM/NCF/NNM,
  plus all connecting edges. All additions predate the anchored trailing-12-month feature
  window, so every previously verified advisor figure is byte-identical (verified by rerun).
- New vertex `phx_dm_coaching_task` (90 seed rows) + edges `phx_dm_coaching_task_for_advisor`
  and `phx_dm_coaching_task_assigned_by` (with reverse edges), backing the manager-assigns-
  coaching-task feature: schema, catalog, loading jobs LOAD-183..185, manifest orders 183-185.
- Totals now 57 vertex types / 128 directed (+128 reverse) edges / 185 manifest CSVs /
  154,946 rows. Validators updated to the new deliberate baseline; full static, business-
  scenario, loading-job, query-case and mock-ingestion suites PASS.
- Reproducible via `scripts/expand_sample_data_v1_2.py` (deterministic, idempotent).

## v0.2.0 — acceptance-gated rebuild

- Replaced the prior GSQL scaffolding with 43 substantive query implementations.
- Added 43 deterministic query invocation cases with required output-key assertions.
- Added query-case validation against sample IDs, enum domains, date ranges and persona authorization paths.
- Added static GSQL semantic validation for edge direction, endpoint types and attributes.
- Added a query audit for parameter use, traversal, aggregation and test coverage.
- Added explicit reverse edges for all 126 directed relationships.
- Added 182 schema-aligned server-side GSQL loading jobs.
- Corrected the RESTPP loader to use manifest column mappings and exact accepted-row counts.
- Added recursive batch isolation, retry, pause/resume, file hashes and checkpoints.
- Added 33 previously absent sample-data targets and ensured every manifest target is nonempty.
- Expanded data to 109,328 rows with all planned personas and scenarios.
- Added AI Ops persona, full CRM status variation, AGP status variation, memory taxonomy and all feedback actions.
- Added Info, Attention, Urgent and Critical coverage for predictions, opportunities and recommendations.
- Added 48 automated business-scenario checks.
- Added full mock ingestion plus unchanged-file reload validation.
- Made live mode the default and mock mode explicitly opt-in.
- Added live installation and RESTPP validation scripts.
- Added package-status, validation and live runbook documentation.
