# Round 5 — Operator Acceptance Checklist (live TigerGraph, real data)

Run these steps **in order** on the client machine against **live TigerGraph** with
`DATA_SET=real`. This is the half of the Round 5 verification that could not be run
in the build environment (no TigerGraph, no client data there). Every step names
the exact command, the expected result, and what to do if it fails.

Prerequisite: `.env` has `GRAPH_CLIENT_MODE=real`, `DATA_SET=real`, valid TG_*
credentials; backend running on 8001, frontend on 3001.

---

## 1. Drop + recreate the schema, install the queries

```bash
gsql docs/tigergraph_foundation/tigergraph/schema/90_drop_all.gsql
gsql docs/tigergraph_foundation/tigergraph/schema/01_vertices.gsql
gsql docs/tigergraph_foundation/tigergraph/schema/02_edges.gsql
gsql docs/tigergraph_foundation/tigergraph/schema/03_create_graph.gsql
gsql docs/tigergraph_foundation/tigergraph/queries/install_all_queries.gsql
```

**Expect:** each drop reports success (or "does not exist" — fine on a clean box);
creates succeed; query install ends with all queries installed.
**On failure:** read the first failing statement's error; a "still in use" error
means the graph drop at the top of 90_drop_all did not run — re-run the script
from the top.

## 2. Clear checkpoints; confirm the resolved DB path

```bash
curl -X POST http://localhost:8001/ingestion/clear-checkpoints
```

**Expect:** `{"cleared_entities": 45, ...}`. Then restart the backend and check the
startup log (logs/app.log) for the `Resolved paths:` line — the `sqlite_db` path is
the ABSOLUTE checkpoint DB actually in use (also shown on the env-health screen
under "resolved_paths"). It must be inside this repo, regardless of the directory
you launched from.
**On failure:** if the endpoint 404s, the backend is an old build — redeploy the
Round 5 files (docs/ROUND5_CHANGED_FILES.md).

## 3. Build the real data set

```bash
python scripts/build_real_data.py
```

**Expect:** the summary prints reconciliation **$0.00 on every transition** and a
MIX share per transition; the first transition (out of the baseline month) shows a
`BASELINE_LIMITED` driver instead of NEW/LOST-account drivers, and its MIX is
below 15%.
**On failure:** the script names the missing raw extract or column; regenerate the
raw extracts per RUNBOOK Step 4 and re-run. A ReconciliationError is a stop
condition — report it, do not proceed.

## 4. Run All; confirm every entity reaches VALIDATED

Open the ingestion screen (Operations → Ingestion) → **Run All**. Watch the live
per-entity progress. When it completes, check the **Validation** column, or:

```bash
curl http://localhost:8001/ingestion/validation | python -m json.tool | grep -E '"state"|"entity_name"' | paste - -
```

**Expect:** all 45 entities `VALIDATED` (graph count == CSV count AND sampled rows
carry populated non-key attributes). `EMPTY_ATTRS` anywhere = the Round 5 defect —
stop and report.
**On failure:** expand the failing entity's row for the error and remediation;
`MISMATCH` with a checkpoint conflict → clear checkpoints (step 2) and re-run that
entity; a column error → regenerate with build_real_data.py.

## 5. Spot-check one vertex in GSQL

```gsql
USE GRAPH iperform_v2_revenue
SELECT * FROM phx_dm_v2_advisor LIMIT 3
```

**Expect:** rows show populated attributes (advisor_name, rep_code, data_source…),
NOT just the id.
**On failure:** that is EMPTY_ATTRS — report which entity, and attach the
ingestion screen's error detail for it.

## 6. Delete-one and delete-all

On the ingestion screen: delete a single entity (e.g. `advisor`), then Delete All.

**Expect:** no 500 / no browser "CORS error"; each returns a per-entity report
(`outcome: deleted|failed` with a reason). A failing entity does NOT abort the
rest.
**On failure:** the JSON error now carries the real message — attach it. The
guaranteed fallback is the clean-slate reset (RUNBOOK Step 10).

## 7. Re-run Run All; confirm idempotency

Load everything again (after step 6's delete-all, re-run Run All twice).

**Expect:** first run re-creates everything and reaches all-VALIDATED again; the
second run reports every row `skipped (Unchanged)`, counts unchanged, still
all-VALIDATED — no duplicates, no false skips.
**On failure:** rows re-created on the second run mean hash state was not written —
check step 2's DB path is stable; rows skipped while the graph is empty mean stale
checkpoints — clear and re-run.

---

When all 7 pass, work-stream A is accepted against live TigerGraph. Record the
outcome (date + any deviations) in BUILD_REPORT.md's Round 5 section.
