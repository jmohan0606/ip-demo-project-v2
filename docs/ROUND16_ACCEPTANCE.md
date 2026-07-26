# ROUND 16 ACCEPTANCE — per-advisor version/scan primary-key collision fix

Round 16 (FIX_SPEC_R16.md) fixed the CRITICAL bug where "Generate all advisors"
and "Rescan all" left the AI Insights and Anomalies screens EMPTY for every
advisor except the last. This document is the operator's checklist for the
client machine: what changed, the **mandatory data migration** (the live graph
holds collided, corrupt version/scan vertices), and how to prove the fix.

Everything below that runs against live TigerGraph / real data is
**OPERATOR-LOCAL** — it could not be executed in the build environment. The
fix itself is proven here on the sample set: `scripts/verify_round16.py`
43/43 PASS across the full 3-advisor matrix (bulk generate-all ×2, bulk
rescan-all, single-advisor runs, dangling-reference audit).

---

## 1. What was broken (root cause)

`phx_dm_v2_commentary_version` has `PRIMARY_ID version_id` and the workflow
wrote `version_id = "v{version_no}"` from a **global** sequence. In a bulk
"generate all" run every advisor received the SAME primary id ("v1", "v2", …),
so each advisor's version-vertex upsert **overwrote the previous advisor's** —
only the last advisor's version vertex survived. The commentary ROWS survived
(their ids embed the advisor), but with no version vertex to resolve,
`get_commentary` returned nothing and the screen showed "no commentary".

`phx_dm_v2_anomaly_scan` (`PRIMARY_ID scan_id`, `scan_id = "scan{n:03d}"`) had
the identical collision on "Rescan all".

## 2. What changed (round 16)

**Write layer (the root cause):**
- Commentary: `version_id = "v{version_no}|{advisor_sid}"`; `version_no` is a
  **per-advisor** sequence (max of that advisor's versions + legacy global
  `advisor_sid=""` rows). Two advisors can both be at v3 — their ids still
  never collide.
- Anomalies: `scan_id = "scan{n:03d}|{advisor_sid}"`; scan number per advisor.
- Every dependent id (`commentary_id`, `evidence_id`, judge `evaluation_id`,
  `anomaly_id`) embeds the version/scan id and inherits the scoped format
  automatically. Supersede now applies only to the advisor's own prior
  PUBLISHED versions and works identically on both tiers.

**Read layer (kept + confirmed):**
- The earlier `SumAccum→MaxAccum` fix in `get_commentary` (R15.1) is **KEPT —
  not reverted**. It is necessary (a summed version_no resolves to a
  non-existent version) but was not sufficient alone, because the write
  collision meant the data it needed was never persisted.
- `get_commentary` / `get_commentary_versions` / `get_anomalies` /
  `get_anomaly_scans` all resolve the latest version/scan **per advisor**
  (the given advisor's rows + legacy global `""`), and read the resolved id
  from the winning vertex itself — never reconstructed.

## 3. NO SCHEMA ALTER IS NEEDED — confirmed

The schema definitions are unchanged: `phx_dm_v2_commentary_version` keeps
`PRIMARY_ID version_id STRING` and `phx_dm_v2_anomaly_scan` keeps
`PRIMARY_ID scan_id STRING` (see `01_vertices.gsql` lines 225 / 319 — not
touched this round). Only the **VALUE format** written into those existing
STRING ids changed (`"v3"` → `"v3|Z166924"`). **No `ALTER VERTEX`, no schema
drop/recreate, no loading-job change.** The migration below is a **data
refresh only**.

## 4. MANDATORY: reinstall the four read queries (live GSQL)

The live install was already flagged divergent in R15.1 (a SumAccum copy of
GQ-009). Reinstall the repo versions of all four before the data migration:

```bash
gsql docs/tigergraph_foundation/tigergraph/queries/GQ-009_get_commentary.gsql
gsql docs/tigergraph_foundation/tigergraph/queries/GQ-010_get_commentary_versions.gsql
gsql docs/tigergraph_foundation/tigergraph/queries/GQ-018_get_anomalies.gsql
gsql docs/tigergraph_foundation/tigergraph/queries/GQ-019_get_anomaly_scans.gsql
```

(Each file is self-contained: `USE GRAPH iperform_v2_revenue`, `CREATE QUERY`,
`INSTALL QUERY`. If a query already exists, `DROP QUERY <name>` first.)

Contract to verify in the installed copies:
- `get_commentary`: `@@latest_no` is a **MaxAccum** (never SumAccum), and the
  advisor filter `(v.advisor_sid == "" OR v.advisor_sid == advisor_id)`
  appears in **both** the accumulate pass and the id read-back pass.
- `get_anomalies`: the advisor filter appears in **both** scan passes (s1 and
  s2) — a copy that MaxAccums `started_at` across ALL scans resolves every
  advisor to the last writer's scan.

## 5. MANDATORY DATA MIGRATION — clear the collided vertices, regenerate

The live graph contains collided version/scan vertices (only the last
advisor's survive) and commentary/anomaly rows attached to ids that no longer
resolve. They are corrupt as a set: **clear and regenerate.** This is a
TARGETED delete of the derived workflow entities — revenue transactions,
months, advisors, drivers, changes, evidence of the underlying data are NOT
touched. Versions are normally additive (CLAUDE.md §7); this one-time clear is
sanctioned because the collided rows are the corrupt output of the bug itself.

### 5a. Clear in the graph (pick ONE method)

**Method 1 — ingestion API (preferred; both tiers, ordered, logged):**

```bash
# anomalies first (they point at scans), then scans;
# evaluations first (they point at commentary), then commentary, then versions
curl -X POST http://localhost:8001/ingestion/delete/anomaly
curl -X POST http://localhost:8001/ingestion/delete/anomaly_scan
curl -X POST http://localhost:8001/ingestion/delete/commentary_evaluation
curl -X POST http://localhost:8001/ingestion/delete/commentary
curl -X POST http://localhost:8001/ingestion/delete/commentary_version
```

(Entity names are the short registry names — `anomaly`, not
`phx_dm_v2_anomaly`; check `GET /ingestion/delete-plan` for the full
list. Each call answers 200 with a per-entity report and clears that entity's
checkpoints.)

(Deleting a vertex in TigerGraph deletes its edges — `anomaly_in_scan`,
`anomaly_for_advisor`, `anomaly_cites_driver`, `commentary_in_version`,
`commentary_for_advisor`, `commentary_from_month`, `commentary_to_month`,
`commentary_cites_driver`, `evaluation_of_commentary` — automatically.)

**Method 2 — GSQL (equivalent, committed script):**

```bash
gsql docs/tigergraph_foundation/tigergraph/schema/91_clear_commentary_anomalies.gsql
```

The script is self-contained (CREATE + INSTALL + RUN + DROP of a one-shot
`clear_commentary_anomalies` query). It deletes the edges explicitly FIRST
(anomaly_for_advisor / anomaly_in_scan / anomaly_cites_driver /
evaluation_of_commentary / commentary_for_advisor / commentary_from_month /
commentary_to_month / commentary_in_version / commentary_cites_driver /
evidence_for_driver, + reverse twins), then the vertices in dependency order
(anomaly → anomaly_scan → commentary_evaluation → commentary →
commentary_version → evidence). It also clears `phx_dm_v2_evidence` — evidence
is rebuilt in full by the next generate-all, so no stale evidence survives.
It touches NO source/revenue data and drops NO schema object.

Note: `phx_dm_v2_commentary_evaluation` (judge verdicts) is cleared with
commentary because its rows reference `commentary_id`/`version_id` — keeping
them would leave dangling references. `phx_dm_v2_evidence` is keyed by
driver+version; rows naming cleared versions become unreachable through the
version selector and are harmless, but you MAY also clear
`phx_dm_v2_evidence` for a fully clean regeneration (it is fully rebuilt by
generate-all).

### 5b. Reset the workflow CSVs in the active data set (`data/real/`)

The dual-persistence CSVs would otherwise re-load the collided rows on the
next manifest run. Truncate each to its HEADER LINE ONLY (keep the file, keep
the header):

```
data/real/vertices/phx_dm_v2_commentary_version.csv
data/real/vertices/phx_dm_v2_commentary.csv
data/real/vertices/phx_dm_v2_commentary_evaluation.csv
data/real/vertices/phx_dm_v2_anomaly_scan.csv
data/real/vertices/phx_dm_v2_anomaly.csv
data/real/edges/phx_dm_v2_commentary_in_version.csv
data/real/edges/phx_dm_v2_commentary_for_advisor.csv
data/real/edges/phx_dm_v2_commentary_from_month.csv
data/real/edges/phx_dm_v2_commentary_to_month.csv
data/real/edges/phx_dm_v2_commentary_cites_driver.csv
data/real/edges/phx_dm_v2_evaluation_of_commentary.csv
data/real/edges/phx_dm_v2_anomaly_in_scan.csv
data/real/edges/phx_dm_v2_anomaly_for_advisor.csv
data/real/edges/phx_dm_v2_anomaly_cites_driver.csv
```

e.g. `head -1 file.csv > file.csv.tmp && mv file.csv.tmp file.csv` for each.
(If you also cleared evidence in 5a, truncate
`vertices/phx_dm_v2_evidence.csv` and `edges/phx_dm_v2_evidence_for_driver.csv`
the same way.)

### 5c. Regenerate everything

From the UI: **AI Insights → "Regenerate (all advisors)"**, then
**Anomalies → "Rescan (all advisors)"**. Or headless:

```bash
python -m app.v2.commentary.generation_workflow          # generate-all
python -m app.v2.anomalies.detection                     # rescan-all
```

## 6. Acceptance drill (live)

1. After generate-all completes, for EACH advisor run:
   `RUN QUERY get_commentary_versions("<advisor_sid>")` — expect at least one
   PUBLISHED version whose `version_id` ends `|<advisor_sid>` and whose
   `advisor_sid` attribute matches. **Count of version vertices ==
   number of advisors** (× versions each) — never collapsed to one advisor.
2. `RUN QUERY get_commentary("<advisor_sid>", "")` for EACH advisor — expect
   that advisor's rows and `resolved_version` = its own scoped id (NOT the
   last advisor's).
3. After rescan-all, `RUN QUERY get_anomaly_scans("<advisor_sid>")` — each
   advisor has its own scan (`scan_id` ends `|<advisor_sid>`);
   `get_anomalies("<advisor_sid>", "", "", 500)` returns that advisor's rows.
4. UI walk: for EVERY advisor in the selector, AI Insights shows commentary
   and Anomalies shows that advisor's scan — not only the last advisor.
5. Regenerate ONE advisor; confirm the others' resolved versions are
   unchanged (single-advisor runs never clobber others).
6. Run a second generate-all: each advisor now has 2 scoped versions —
   latest PUBLISHED, prior SUPERSEDED — independently per advisor.

## 7. What was NOT changed (regression guard)

- No computed figure, attribution step, taxonomy path, or eligibility rule —
  reconciliation stays $0.00 (verify_end_to_end re-run PASS).
- The R11 per-advisor SCOPE model (buttons, advisor_sid attributes, selector
  filters) is unchanged — this round fixed the KEY so that scoping works.
- The R15.1 MaxAccum fix in get_commentary is KEPT.
- Rounds 9–15 suites all re-run PASS (assistant 101/101, guardrail 54/54,
  role 32/32, gpt5 34/34, per_advisor 33/33, judge 9/9, retry 10/10,
  glossary 7/7, commentary_version 16/16, round15 25/25, attribution,
  taxonomy, eligibility, new_drivers, clawback, anomalies, e2e recon $0.00).
