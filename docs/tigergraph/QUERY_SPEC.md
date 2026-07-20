# QUERY SPEC — iPerform V2

Location: `docs/tigergraph_foundation/tigergraph/queries/`
Files: `GQ-0NN_<snake_name>.gsql` · catalogue: `query_catalog.json` ·
installer: `install_all_queries.gsql` · test params: `tests/query_cases.json`

---

## 1. GSQL SYNTAX RULES — non-negotiable

These were learned the hard way on a live TigerGraph 4.2.x. Queries violating them **fail
to install**, and you cannot test that here.

1. **Parameters are type-first.**
   WRONG `CREATE QUERY q(advisor_id STRING)` · RIGHT `CREATE QUERY q(STRING advisor_id)`
2. **Traversal targets are vertex TYPES, with edge aliases.**
   WRONG `-(edge:e)- all_advisors:a` · RIGHT `-(phx_dm_v2_txn_for_advisor:e)- phx_dm_v2_advisor:a`
   (A vertex-set variable as the traversal *source* is fine; as the *target* it is not.)
3. **One hop per SELECT.** Multi-hop must be split into consecutive SELECT statements.
4. Declare `SYNTAX V1`, start with `USE GRAPH iperform_v2_revenue`, end with
   `INSTALL QUERY <name>`.
5. The plain `-(edge:e)- vtype:v` form **is** valid V1 — do not "correct" it to `-(edge)->`.
6. Use `phx_dm_v2_` prefixes everywhere.

**Accumulator caution:** `SumAccum<STRING>` concatenates. Only use it where the value is
1:1 with the row (e.g. one product per transaction). For counts and sums use
`SumAccum<INT>` / `SumAccum<DOUBLE>`; for maps use `MapAccum<STRING, SumAccum<DOUBLE>>`.

---

## 2. RESULT SHAPE

Vertex-set prints return `{"v_id":…, "v_type":…, "attributes":{…}}`. Readers access via
`row.get("attributes", {})`.

**The local-tier (SQLite) implementation of every query MUST return the identical nested
shape.** This is what makes local verification meaningful. Register them with
`@mock_query("<name>")` in `app/graph/queries/`, following
`docs/v1_patterns/EXAMPLE_mock_query_impls.py`.

For `PRINT @@map` style outputs, return the plain map exactly as RESTPP would.

---

## 3. THE QUERIES

Author all of these. Each needs: `.gsql` file · catalog entry · local-tier implementation ·
an entry in `tests/query_cases.json` with working parameters.

### Reference / dimension

**GQ-001 `get_advisors`** `()` → all advisors (id, name, rep_code, branch). *Advisor picker.*

**GQ-002 `get_months`** `()` → months in scope, ordered, with `prior_month_id`,
`calendar_days`, `billable_days`. *Period controls, transition list.*

**GQ-003 `get_product_hierarchy`** `()` → class → line → group → product, with display
order. *Pivot row structure.*

**GQ-004 `get_driver_causes`** `()` → the cause vocabulary. *Legend, filters.*

### Trends screens

**GQ-005 `get_monthly_revenue_by_product`** `(STRING advisor_id, STRING from_month, STRING to_month)`
→ one row per (month, group): revenue, txn_count, recurring/one-time split, plus
group→line→class ids. **Powers `01_trends_revenue_by_month`.** Read from
`phx_dm_v2_monthly_product_revenue` — do not scan transactions.

**GQ-006 `get_monthly_revenue_totals`** `(STRING advisor_id, STRING from_month, STRING to_month)`
→ per month: total revenue, recurring total, non-recurring total, txn_count.
**Powers the stacked bar chart on `03_ai_insights_walk`.**

**GQ-007 `get_revenue_changes`** `(STRING advisor_id, STRING from_month, STRING to_month)`
→ every `phx_dm_v2_revenue_change` for the advisor in range, including the `__TOTAL__` rows.
**Powers `02_trends_mom_change` and the chart arrows.**

### Drivers & commentary

**GQ-008 `get_change_drivers`** `(STRING advisor_id, STRING from_month, STRING to_month, INT result_limit)`
→ drivers for that transition, ranked by |contribution|, each with cause, group,
contribution amt/pct, direction, `data_source`, `inputs_json`.
**Powers the ✓/✗ bullets.**

**GQ-009 `get_commentary`** `(STRING advisor_id, STRING version_id)`
→ commentary rows for every transition in that version: headline, narrative, bullets,
status. `version_id = ""` means latest PUBLISHED.
**Powers `03_ai_insights_walk` cards and `06_ai_commentary_table`.**

**GQ-010 `get_commentary_versions`** `()` → all versions with status and counts, newest
first. *Version selector.*

### Evidence & drill-down

**GQ-011 `get_product_revenue_change`** `(STRING advisor_id, STRING product_group, STRING from_month, STRING to_month)`
→ `{from_revenue, to_revenue, change, txn_count}`.
**This is the query printed in the evidence modal's "Reproduce this result" section — it
must be genuinely runnable and return exactly the figures shown.**

**GQ-012 `get_evidence`** `(STRING driver_id, STRING version_id)`
→ the full evidence record: finding, calc, source records, lineage, checks, gsql
name/params/result, source SQL, source table, row count.

**GQ-013 `get_transactions`** `(STRING advisor_id, STRING month_id, STRING group_id, INT result_limit)`
→ transaction rows: trade_ref, dates, product, account, credited amt, split %, file_key,
rev_nature. **Powers the Transactions drill-down** reached by clicking a pivot figure or a
commentary bullet. `group_id = ""` means all groups.

### Operations

**GQ-014 `get_ingestion_counts`** `()` → per V2 vertex type: count + `data_source` mix.
*Ingestion screen loaded-counts, env-health reconciliation.*

**GQ-015 `get_advisor_month_summary`** `(STRING advisor_id)` → per month: total revenue,
txn count, distinct products, distinct accounts. *Header context bar, sanity checks.*

---

## 4. CATALOG ENTRY FORMAT

```json
{
  "id": "GQ-005",
  "name": "get_monthly_revenue_by_product",
  "file": "GQ-005_get_monthly_revenue_by_product.gsql",
  "parameters": [
    {"name": "advisor_id", "type": "STRING", "required": true},
    {"name": "from_month", "type": "STRING", "required": true},
    {"name": "to_month",   "type": "STRING", "required": true}
  ],
  "purpose": "Monthly credited revenue by product group for the Trends pivot.",
  "outputs": "monthly_revenue: vset rows {month_id, group_id, line_id, class_id, revenue, txn_count, recurring_amt, one_time_amt}",
  "consumers": ["app/v2/revenue/monthly_service.py", "GET /api/v2/trends/revenue"],
  "status": "created-v2-NEEDS-LIVE-INSTALL"
}
```

Every query starts at `status: "created-v2-NEEDS-LIVE-INSTALL"` — nothing here has been
installed on a live graph. Flag them all as client-machine follow-ups in `BUILD_REPORT.md`.

---

## 5. IF YOU NEED A QUERY THAT ISN'T LISTED

Allowed and expected. Deliver it as one unit:
1. `.gsql` file at the next free number, obeying §1
2. `query_catalog.json` entry (§4)
3. Local-tier implementation returning the identical shape (§2)
4. Entry in `tests/query_cases.json` with working parameters
5. Added to `install_all_queries.gsql`
6. Recorded in `BUILD_REPORT.md` under "New queries created"

**Never** call `run_query` with a name that is not in the catalog.

---

## 6. VERIFICATION AVAILABLE HERE

You cannot install or run these against TigerGraph in this environment. What you **can** and
**must** do:
- Every query parses cleanly against the §1 rules (check each file explicitly).
- Every referenced vertex/edge type exists in `SCHEMA_SPEC.md` — a typo here means an
  install failure the client will hit, not you.
- Every query has a local-tier implementation and returns the same keys, verified by
  exercising the reader in both `GRAPH_CLIENT_MODE=local` and `real` (both serve locally
  here) and diffing the output shape.
- `tests/query_cases.json` parameters resolve against the sample data set.
