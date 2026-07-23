# iPerform V2 — Operations Runbook

**Standalone setup guide for the client machine.** This is the do-this-exactly sequence
to stand up iPerform V2 with real data on a live TigerGraph. Each step gives the exact
command, the expected output, and the failure symptom with the first thing to check.

> This runbook is extracted from `docs/SOLUTION_GUIDE.md` Chapter 9 for convenience during
> setup. The SOLUTION_GUIDE remains the full reference (schema, calculations, architecture,
> known gaps); this file is only the operational sequence.

---

## Before you start — what is proven and what is not

Read this once so nothing surprises you mid-setup:

- **Real data is the only demo path.** Everything below assumes `DATA_SET=real`;
  the sample set is a test asset for the automated verification scripts only.
- **Steps 4–8 (extract → build → load → generate → verify) are proven on the local SQLite
  tier.** The transform, reconciliation, ingestion contract and commentary generation all
  work. Round 5 additionally proved the ingestion fixes (attribute integrity, fail-loud
  header mismatch, checkpoint honesty, guarded deletes, idempotency) with the fixture
  harness: `python scripts/make_ingestion_fixtures.py && python scripts/verify_ingestion_fixes.py`.
- **First live load after round 5:** run `docs/ROUND5_ACCEPTANCE.md` — it verifies on
  live TigerGraph what the fixture harness can only prove locally, ending with every
  entity `VALIDATED` on the ingestion screen.
- **Steps 2–3 (schema + query install) and the tier-1 graph load have NOT yet run against a
  live TigerGraph.** All 15 GSQL queries are marked `NEEDS-LIVE-INSTALL`. This is expected —
  the first live install is where a query that parses locally may still need adjustment on
  TigerGraph 4.2.x. If an install fails, capture the exact error; it is a fixable install
  issue, not a design problem.
- **Delete/reload (Step 9)** has been exercised only on the local tier; note the RESTPP
  edge-delete caveat in that step.

Keep the console output of Steps 2, 3 and 6 on the first run — if anything fails, that
output is what pinpoints it.

---

## Prerequisites checklist

- [ ] TigerGraph reachable from this machine (host, port, credentials known)
- [ ] Python and Node versions per Step 1
- [ ] `.env` created from `.env.example` with all keys filled (`GRAPH_CLIENT_MODE=real`,
      `DATA_SET=real`, `TG_*`, `ANTHROPIC_API_KEY`)
- [ ] PostgreSQL access to run the 3 extraction SQLs
- [ ] Repo cloned and dependencies installed

---

### Step 1 — Prerequisites

1. **Python 3.11+** (`python --version`) and **Node 20+** (`node --version`).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   cd frontend && npm install && cd ..
   ```
3. **TigerGraph 4.2.x reachable** from this machine (`curl -k https://<host>:14240/api/ping`).
4. Create the env file: `cp .env.example .env`, then fill in the top blocks —
   `GRAPH_CLIENT_MODE=real`, `DATA_SET=real`, `LLM_CLIENT_MODE=claude`,
   `ANTHROPIC_API_KEY`, and the `TG_*` connection values. Every key the backend reads
   is in the template with its default.
5. `python scripts/runtime_preflight.py` — sanity-checks the runtime.

**Failure symptom:** backend later boots but env-health shows tier 2 RED in real mode
→ first check the `TG_*` values and step 1.3's ping.

### Step 2 — Install the schema (once per graph)

Run against TigerGraph, in this order (gadmin console, GraphStudio's GSQL editor, or
`gsql` CLI):

```bash
gsql docs/tigergraph_foundation/tigergraph/schema/01_vertices.gsql
gsql docs/tigergraph_foundation/tigergraph/schema/02_edges.gsql
gsql docs/tigergraph_foundation/tigergraph/schema/03_create_graph.gsql
```

**Expect:** 18 vertex types + 27 edge types created; graph `iperform_v2_revenue`.
**Failure:** "used by another graph" → the types already exist; drop the old graph or
skip to step 3. Any parse error → confirm TigerGraph version is 4.2.x.

### Step 3 — Install the queries (the step that proves them)

```bash
gsql -g iperform_v2_revenue docs/tigergraph_foundation/tigergraph/queries/install_all_queries.gsql
```

**Expect:** all queries (GQ-001..GQ-017) install successfully.
**Note:** every query file is flagged `created-v2-NEEDS-LIVE-INSTALL` — parse-verified
in the build environment, never yet installed on a live TigerGraph. **This is the step
that proves them**; report any installer error verbatim.
**Failure:** a single query fails to install → run `python scripts/validate_v2_queries.py`
locally to confirm catalog/file consistency, then inspect that GQ file.

### Step 4 — Extract the data (human-run SQL → raw CSVs)

1. Run the three SQLs in `docs/data/extraction/` against PostgreSQL `pcr` (fpicdb) in
   your SQL client, and save each result as CSV **with a header row** to exactly:
   ```
   data/real/_raw/raw_revenue_transaction.csv   ← extract_revenue_transaction.sql
   data/real/_raw/raw_product_hierarchy.csv     ← extract_product_hierarchy.sql
   data/real/_raw/raw_advisor.csv               ← extract_advisor.sql
   ```
   The expected columns are the SELECT lists of those SQLs (also codified in
   `scripts/build_real_data.py` → `RAW_CONTRACT`).
2. Scope changes (months, advisor list): edit `docs/data/source_catalog.json` and
   regenerate the SQL with `python scripts/generate_extraction_sql.py` — never
   hand-edit the SQL files.
3. Verify `advisor_sid` on the trade table equals `standard_id` in `fpic_prm_rr_tb`;
   fall back to (`prm_ofc_no`, `prm_rr_no`) if not. Blank advisor names are fine —
   the app displays the id, it never invents a name.

**Failure:** step 5 names the missing file/column — re-export with headers, comma
separators, UTF-8.

### Step 5 — Build `data/real/` from the raw extracts

```bash
python -m scripts.build_real_data          # defaults: --raw data/real/_raw --out data/real
```

**Expect:** a per-file row-count table, the eligibility split, OUT_OF_GRID and
>90-day counts, `Reconciliation: $0.00 on every transition ✓`, and a MIX% line per
transition (MIX should be small — a large MIX means a named driver is missing).
The script reuses the app's own aggregation/attribution code and stamps
`data_source` on every row; it regenerates the ingestion manifest scoped to this set.
**Failure — the build STOPS, by design:**
- *missing raw extract / missing column* → step 4's save didn't match the contract.
- *months not consecutive* → extract the missing month or narrow the date range.
- *transactions reference products/advisors missing from the other extracts* →
  re-run the hierarchy/advisor SQL; they must cover the trade extract.
- *RECONCILIATION FAILED* → **stop; do not load.** This means the driver maths did
  not account for every dollar on real data. Capture the printed discrepancy JSON
  and investigate (`app/v2/drivers/attribution.py`) before proceeding.

### Step 6 — Load the graph

With the backend running (step 8 starts it; you can start it now):
Data Ingestion screen → **Run all**, or headless:

```bash
curl -X POST http://localhost:8001/ingestion/run-all
curl http://localhost:8001/ingestion/run-all/status      # poll (async; safe to re-GET)
curl http://localhost:8001/ingestion/validation          # graph-truth check per entity
```

**Expect:** every manifest entity loads in dependency order and ends `VALIDATED` in
the screen's Validation column — graph count equals the source CSV's row count AND
sampled rows carry populated non-key attributes. `EMPTY_ATTRS` or `MISMATCH`
anywhere = stop and expand that row for the error and remediation.
Commentary/evidence files load 0 rows on a fresh set — that is correct; they are
created by step 7.
**Failure:** a count mismatch names the entity — check that step 5 completed after
the last extract change (stale `data/real/` vs manifest).

### Step 7 — Generate commentary (the ONLY trigger)

**A fresh environment has no commentary until this runs.** Page loads only retrieve.
Either: AI-Insights screen → **Regenerate** button, or headless (client environments
without a browser):

```bash
python -m app.v2.commentary.generation_workflow --notes "initial real-data run"
```

**Expect:** a JSON summary — `published` = advisors × transitions, `blocked: 0`,
one evidence record per driver, judge tallies (advisory only). Each run creates a NEW
version; prior versions are never deleted.
**Failure:** `blocked > 0` → that transition's guardrail reason is stored and shown
plainly in the UI; the other transitions still publish. LLM errors → check
`ANTHROPIC_API_KEY`, or set `LLM_CLIENT_MODE=mock` to prove the pipeline first
(deterministic sentences, identical gates).

### Step 8 — Run and verify

```bash
./scripts/run_api.sh                        # backend, port 8001
cd frontend && npm run dev                  # frontend, port 3001
```

Then verify, in order:
1. **Env-health screen** (`/env-health`): `active_tier=1`, `served_by_tier=1`, green.
   **RED means the local store is serving in real mode — investigate before trusting
   anything else** (fallback is logged, never silent).
2. **Spot-check a pivot total** (`/trends`): pick one advisor × month and tie it to
   your source query: `SELECT SUM(post_split_credited_amt) FROM
   pcr.fpic_daily_trade_details_tb_prod WHERE advisor_sid='...' AND
   to_char(trade_dt,'YYYYMM')='...'` (remember: the pivot shows CREDITED revenue —
   eligible reason codes, credited grid types, ≤90-day processing).
3. **Open an evidence modal** (AI-Insights → any "View evidence ›"): header change,
   group-scoped waterfall FROM→TO and credited breakdown must all equal the same
   group-level figure.
4. `curl "http://localhost:8001/api/v2/ops/reconciliation?advisor_id=<sid>&from_month=<YYYYMM>&to_month=<YYYYMM>"`
   → `all_reconcile: true`, discrepancy `0.0` per transition.
5. `python scripts/verify_end_to_end.py` → `OVERALL: PASS`.

### Step 9 — Reload / reset (ordered delete)

To reload after a new extract:

```bash
curl http://localhost:8001/ingestion/delete-plan       # review the plan
curl -X POST http://localhost:8001/ingestion/delete-all
```

Delete runs in REVERSE dependency order (analytics → facts → dimensions); the confirm
dialog on the ingestion screen shows the same plan. Then repeat steps 4–7.
Delete-all never aborts on a failing entity: it returns a per-entity report
(`outcome: deleted|failed` + reason). Checkpoints are cleared per *confirmed*
entity so a stale checkpoint can never suppress a re-load.
**Caveat on live TigerGraph:** RESTPP/pyTigerGraph cannot bulk-delete edges — edges
disappear when their endpoint vertices are deleted; the delete report states this.

### Step 10 — Clean-slate reset (guaranteed, manual — use when delete-all cannot be trusted)

When the graph and the checkpoints disagree, or a load has left partial state you
cannot reason about, reset from zero. This always works because it rebuilds the
schema itself:

1. **Drop everything** (edges → vertices → graph, correct order):
   ```bash
   gsql docs/tigergraph_foundation/tigergraph/schema/90_drop_all.gsql
   ```
2. **Recreate the schema and queries:**
   ```bash
   gsql docs/tigergraph_foundation/tigergraph/schema/01_vertices.gsql
   gsql docs/tigergraph_foundation/tigergraph/schema/02_edges.gsql
   gsql docs/tigergraph_foundation/tigergraph/schema/03_create_graph.gsql
   gsql docs/tigergraph_foundation/tigergraph/queries/install_all_queries.gsql
   ```
3. **Clear the ingestion checkpoints** (otherwise every row hash-matches and skips
   as "Unchanged" against the now-empty graph):
   ```bash
   curl -X POST http://localhost:8001/ingestion/clear-checkpoints
   # or one entity: curl -X POST "http://localhost:8001/ingestion/clear-checkpoints?entity_name=advisor"
   ```
   The backend startup log and `/env-health` (`resolved_paths`) show the absolute
   path of the checkpoint SQLite DB actually in use.
4. **Run All** from the ingestion screen and confirm every entity reaches
   `VALIDATED` in the validation-proof column (graph count matches expected AND
   sampled rows carry populated non-key attributes).

