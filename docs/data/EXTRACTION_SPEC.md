# EXTRACTION & COMPUTATION SPEC — iPerform V2

How client data becomes graph data, and how drivers are computed from it.

---

## 1. SOURCE SYSTEM

PostgreSQL, schema `pcr`, database `fpicdb` (UAT). The app **cannot reach it** — a human
runs the extraction SQL and drops CSVs into `data/real/`. Store the SQL anyway: it is shown
in the evidence modal as lineage (§6).

| Table | Gives us |
|---|---|
| `fpic_daily_trade_details_tb` | **The revenue fact.** One row per trade split. ~48M rows total; we take 10 advisors × 3 months. |
| `fpicdb_pcr_product_hierarchy` | product → level_two → level_one, and `grid_type` |
| `fpic_prm_rr_tb` | advisor identity (`standard_id`, `rr_nam`, branch, supervisory chain) |
| `fpic_employee_tb` | advisor display name (`em_standard_id` → `em_name_txt`) |

**Not usable** (checked): `fpic_daily_adv_flows_tb` (stops 2026-01-30) ·
`fpic_monthly_trade_details_tb` (no rows after 2026-04-01) · `fpic_balances_tb`
(margin equity, not billable assets).

### Key facts established by investigation — do not re-derive
- **Credited revenue = `post_split_credited_amt`.** Verified: `pre_split_credited_amt ×
  split_pct = post_split_credited_amt` (e.g. 128.25 × 0.26 = 33.35). Summing `pre_split`
  would double-count across advisors.
- **Filter product joins to `grid_type = 'PRODUCT_TYPE'`** — excludes
  `NON_CREDITED_REVENUE` and `PAY_TYPE_SUMMARY` rows.
- **Revenue month comes from `trade_dt`**, not `proc_dt` (processing runs the day after
  month-end: `trade_dt` 2026-04-30 → `proc_dt` 2026-05-01). `year_month_no` is only 2%
  populated — use it as a cross-check, never as the filter.
- **`avg_balance_amt` is 0% populated for Managed** — see `SCHEMA_SPEC.md` §5.

---

## 2. SCOPE

**Months:** 2026-04-01 ≤ `trade_dt` < 2026-07-01 (Apr, May, Jun 2026) → two transitions.

> April has no prior month in scope, so it shows no commentary — display it as
> "Baseline month — no prior period in the current data set" (see mockup 06). If March data
> is later supplied it is used only to compute April's drivers.

**Advisors — the ten in the demo set:**
`V236209` · `U869485` · `R452497` · `F074537` · `D194202` ·
`Z166924` · `I090694` · `V077477` · `I069872` · `U713250`

Chosen for spread: revenue $0.85M–$1.41M over the quarter, 9–14 product categories, and a
range of clawback volumes (2 → 2,653 negative rows) so every code path is exercised.

> Two known data notes to state in `BUILD_REPORT.md`: a large NULL-`advisor_sid` bucket
> (~$30.5M) exists and is excluded, so firm totals will not tie; and June may be a partial
> month — if so, label it rather than narrating an artefact as a business decline.

---

## 3. EXTRACTION SQL

Store each of these in `docs/data/extraction/` as its own `.sql` file. The evidence modal
renders the relevant one with real parameter values.

**`extract_revenue_transaction.sql`**
```sql
SELECT d.trade_ref_no, d.split_seq_no, d.advisor_sid,
       to_char(d.trade_dt,'YYYYMM')          AS month_id,
       d.product_cd, d.product_sub_cd, d.account_no,
       d.trade_dt, d.proc_dt,
       d.post_split_credited_amt, d.pre_split_credited_amt, d.split_pct,
       d.client_rate_bps, d.std_tier_rate,
       d.concession_type, d.discount_amt, d.eff_disc_pct,
       d.avg_balance_amt, d.file_key, d.trade_description
FROM   pcr.fpic_daily_trade_details_tb d
JOIN   pcr.fpicdb_pcr_product_hierarchy h
       ON  d.product_cd     = h.product_code
       AND d.product_sub_cd = h.sub_product_code
       AND h.grid_type      = 'PRODUCT_TYPE'
WHERE  d.trade_dt >= DATE '2026-04-01'
  AND  d.trade_dt <  DATE '2026-07-01'
  AND  d.advisor_sid IN ('V236209','U869485','R452497','F074537','D194202',
                         'Z166924','I090694','V077477','I069872','U713250');
```

**`extract_product_hierarchy.sql`**
```sql
SELECT DISTINCT product_code, sub_product_code,
       level_two_product, level_one_product,
       level_one_pay_type_product_cd, level_two_pay_type_product_cd
FROM   pcr.fpicdb_pcr_product_hierarchy
WHERE  grid_type = 'PRODUCT_TYPE';
```

**`extract_advisor.sql`**
```sql
SELECT r.standard_id AS advisor_sid, r.rr_nam, r.prm_rr_no AS rep_code,
       r.cwm_branch_cd AS branch_cd, e.em_name_txt AS advisor_name
FROM   pcr.fpic_prm_rr_tb r
LEFT   JOIN pcr.fpic_employee_tb e ON e.em_standard_id = r.standard_id
WHERE  r.standard_id IN ( ...the ten... );
```
> Verify `advisor_sid` on the trade table equals `standard_id` here. If it does not, fall
> back to `(prm_ofc_no, prm_rr_no)`. If names come back blank, display the advisor id — do
> **not** invent names.

---

## 4. CSV → VERTEX MAPPING

`data/{sample|real}/` , one CSV per vertex, named for it. `manifest.json` lists them in
**dependency order** — dimensions, then facts, then analytics. This order is also the load
order and, reversed, the delete order.

| # | CSV | Vertex | Built from |
|---|---|---|---|
| 1 | `advisor.csv` | advisor | `extract_advisor.sql` |
| 2 | `month.csv` | month | Generated (§5) |
| 3 | `revenue_class.csv` | revenue_class | Seeded: RECURRING, NON_RECURRING |
| 4 | `product_line.csv` | product_line | distinct `level_one_product` |
| 5 | `product_group.csv` | product_group | distinct `level_two_product` |
| 6 | `product.csv` | product | distinct `(product_cd, sub_product_code)` |
| 7 | `account.csv` | account | distinct `account_no` |
| 8 | `driver_cause.csv` | driver_cause | Seeded (SCHEMA_SPEC §1) |
| 9 | `revenue_transaction.csv` | revenue_transaction | `extract_revenue_transaction.sql` |
| 10 | `monthly_product_revenue.csv` | monthly_product_revenue | Computed (§6) |
| 11 | `account_month_balance.csv` | account_month_balance | **DUMMY placeholder rows** |
| 12 | `revenue_change.csv` | revenue_change | Computed (§6) |
| 13 | `revenue_driver.csv` | revenue_driver | Computed (§7) |
| 14–16 | commentary_version / commentary / evidence | — | Generated by the workflow, not loaded from CSV |

Edge CSVs follow the same pattern, loaded after their endpoint vertices.

**`rev_nature`** (on each transaction) is derived, not sourced:
- `ADJUSTMENT` if `trade_description` starts with `ADJUSTMENT`, or `file_key = 'manual_adj'`
- `ONE_TIME` if `file_key` in (`twhs`, `l_a_ancomm`, `pb_rfrrl`, `refrl_401k`, `sitn_ptnr`)
  or `trade_description` starts with `ANNUITY ISSUED`
- else `RECURRING` (`ace`, `mf_12b1`, `l_a_btr`, `529_trails`, `money_mkt`, `prem_dep`,
  `sbl_prcing`, `mrgn_lend`)

**Recurring vs non-recurring class:** Recurring = product lines `Managed` and `Trails`;
everything else Non-recurring. *(Inferred from the client mockup — flag for confirmation.)*

---

## 5. MONTH GENERATION

For each month in scope: `month_id` `"YYYYMM"`, year, `month_no` (1–12 — populate properly),
`month_name`, quarter, start/end dates, `calendar_days`, `prior_month_id`.

`billable_days` = business days (Mon–Fri, no holiday calendar available) →
**Apr 2026: 22 · May 2026: 21 · Jun 2026: 22** *(verify when generating)*. Mark `DERIVED`
and make it trivially updatable — the client may replace it with their billing calendar.

`index_return` = `0.0`, `DUMMY`.

---

## 6. AGGREGATION & CHANGE

**Monthly product revenue** — group transactions by (advisor, month, group):
`revenue = Σ credited_amt` · `txn_count` · `account_count = distinct account_no` ·
`avg_rate_bps = Σ(client_rate_bps × credited_amt) / Σ credited_amt` (weighted) ·
`recurring_amt` / `one_time_amt` split by `rev_nature`.

**Revenue change** — for each (advisor, consecutive month pair, group):
```
change_amt = to_revenue − from_revenue
change_pct = change_amt / from_revenue × 100      # if from_revenue = 0 → null, show "n/a"
```
Plus a `group_id = "__TOTAL__"` row per transition (the headline).

---

## 7. DRIVER ATTRIBUTION

For each transition and product group, decompose `change_amt` into causes. Attribute in
this order; each step consumes part of the change, and **the remainder falls to `MIX`** so
contributions always reconcile.

1. **`NEW_ACCOUNT` / `LOST_ACCOUNT`** — accounts present in one month only.
   `contribution = Σ credited_amt` of those accounts. `REAL`
2. **`ONE_TIME`** — `rev_nature = ONE_TIME` in one month but not the other.
   `contribution = to_one_time − from_one_time`. `REAL`
3. **`CLAWBACK`** — change in negative-amount rows. `contribution = to_neg − from_neg`. `REAL`
4. **`TIMING`** — a group with quarterly billing (e.g. Alternatives) present in one month
   only, and not already claimed by ONE_TIME. `REAL`
5. **`FEE_RATE`** — `from_assets_proxy × (to_avg_rate_bps − from_avg_rate_bps) / 10000`,
   where `assets_proxy = from_revenue / (from_avg_rate_bps/10000)`. `REAL`
6. **`DISCOUNT`** — change in `Σ discount_amt`, and change in the count of
   `concession_type='Discount'` rows. `REAL`
7. **`BILLABLE_DAYS`** — recurring/fee-based groups only:
   `from_revenue × (to_billable_days − from_billable_days) / from_billable_days`. `DERIVED`
8. **`VOLUME`** — transaction-based groups: `(to_txn_count − from_txn_count) ×
   from_avg_txn_value`. `REAL`
9. **`MARKET`** — needs `index_return`. Emit with `contribution = 0`, `data_source = DUMMY`.
10. **`NET_FLOW`** — needs a flows source. Emit with `contribution = 0`, `data_source = DUMMY`.
11. **`MIX`** — whatever remains: `change_amt − Σ(all above)`. `DERIVED`

**Reconciliation is mandatory.** `Σ contributions == change_amt` within $1. If not, log the
discrepancy, mark the transition `BLOCKED`, and do not publish its commentary.

**Ranking:** by `|contribution_amt|` descending; `rank` from 1. The UI shows the top 5.

**`inputs_json`** must record every number the attribution used (from/to revenue, counts,
rates, days, account sets) — this is what the evidence modal's calculation table renders.

---

## 8. SAMPLE DATA SET

`data/sample/` ships with the repo (`data/real/` is gitignored). It must be **synthetic and
obviously so** — 3 advisors × 3 months, names like "Sample Advisor One", ids `SMPL001`+.

It must exercise **every driver cause**, including at least one `DUMMY` (MARKET or
NET_FLOW) so the provenance badges are visible without client data. The app must boot,
ingest and render every screen with `DATA_SET=sample` alone.

The UI must show a persistent banner when `DATA_SET=sample`: *"Sample data — not client
figures."*

---

## 9. EVIDENCE LINEAGE (PostgreSQL)

Each evidence record stores the extraction SQL that sourced its rows, with the actual
parameters substituted, plus `source_table` and `source_row_count`.

**Label it precisely in the UI:** the PostgreSQL SQL is shown **for lineage and independent
verification — it is not executed by this application**. The GSQL query, by contrast, *was*
run and its result is displayed. Do not blur that distinction; the client's whole evaluation
concern rests on knowing which numbers were produced versus quoted.
