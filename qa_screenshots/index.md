# QA screenshot evidence

Generated 2026-07-21T16:43:52.252Z against http://localhost:3001 (backend http://localhost:8001), viewport width 1440, sample data set.

This folder is gitignored — regenerate with `node scripts/capture_evidence.mjs` (servers must be running).

| Screenshot | Captured | What it proves | Console errors |
|---|---|---|---|
| `01_trends.png` | yes | Trends screen renders both cards — the revenue pivot by product hierarchy and the month-over-month card — from sample data. | none |
| `02_ai_insights.png` | yes | AI Insights renders the stacked revenue chart, the stored commentary cards (with version selector), and the monthly walk table. Commentary is retrieved, not generated on load. | none |
| `03_evidence_modal.png` | yes | The evidence modal opens from a driver bullet and shows the evidence record for that driver (finding, calculation, source records, lineage, runnable query). Opened via the first 'View evidence' affordance on a commentary bullet. | none |
| `04_transactions_filtered.png` | yes | Transactions drill-down honours URL filters (advisor SMPL001, Jun 2026, Unified Managed Account): filter chips shown, rows restricted, footer credited-revenue total matches the filtered set. | none |
| `05_data_ingestion.png` | yes | Data-ingestion screen renders: load / reload / ordered-delete controls and per-file status for the sample data set. | none |
| `06_env_health.png` | yes | Environment-health screen reports backend connectivity, configured modes, and the true serving tier. | none |
| `07_transactions_empty_state.png` | yes | Empty state: Annuities has no SMPL001 transactions in Jun 2026 (true in the sample data), so the screen shows its 'no transactions match' state rather than fabricating rows. | none |
| `08_commentary_blocked_state.png` | yes | BLOCKED-commentary state: with historical version v3 selected, the SMPL001 May→Jun transition shows its guardrail-blocked card with the block reason — no narrative is shown for a transition that failed validation. Version v3 selected via the UI version selector; v3 contains a guardrail-BLOCKED transition for SMPL001 (May→Jun 2026) in the sample data. | none |

**Result: PASS** — every screen captured with zero browser console errors.
