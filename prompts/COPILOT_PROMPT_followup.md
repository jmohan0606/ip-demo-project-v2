Six of your queries hit statement timeouts. Re-run ONLY the failed ones, rewritten to avoid full
scans. Same output rules as before: fixed template only, no preamble, no plan, under 40 lines,
`FAILED: <reason>` if something still dies, never estimate or infer.

FIRST, raise the timeout for this session:
```sql
SET statement_timeout = '600s';
```

---

## F1 — Do trade and flow accounts join? (sampled, not counted)

Do NOT count all matches. Take a small sample and test membership.

```sql
-- F1a: 100 flow accounts, how many exist in trade (normalised)?
WITH f AS (
  SELECT DISTINCT ltrim(trim(wm_acct_src_nb),'0') AS k
  FROM pcr.fpic_daily_adv_flows_tb_pm
  WHERE wm_acct_src_nb IS NOT NULL AND ltrim(trim(wm_acct_src_nb),'0') <> ''
  LIMIT 100
)
SELECT count(*) AS flow_sample,
       count(*) FILTER (WHERE EXISTS (
         SELECT 1 FROM pcr.fpic_daily_trade_details_tb_prod t
         WHERE ltrim(trim(t.account_no),'0') = f.k
           AND t.trade_dt >= DATE '2026-04-01' AND t.trade_dt < DATE '2026-07-01'
       )) AS found_in_trade
FROM f;

-- F1b: same test against rr_changes and eci_rel
WITH f AS (
  SELECT DISTINCT ltrim(trim(wm_acct_src_nb),'0') AS k
  FROM pcr.fpic_daily_adv_flows_tb_pm
  WHERE wm_acct_src_nb IS NOT NULL AND ltrim(trim(wm_acct_src_nb),'0') <> ''
  LIMIT 100
)
SELECT count(*) FILTER (WHERE EXISTS (
         SELECT 1 FROM pcr.fpic_rr_changes_from_nacs_logs r
         WHERE ltrim(trim(r.account_no),'0') = f.k)) AS found_in_rr,
       count(*) FILTER (WHERE EXISTS (
         SELECT 1 FROM pcr.fpic_acct_eci_rel_tb_pm e
         WHERE ltrim(trim(e.account_number),'0') = f.k)) AS found_in_eci_rel
FROM f;

-- F1c: raw samples still missing from the first run
SELECT account_number FROM pcr.fpic_acct_tb_pm WHERE account_number IS NOT NULL LIMIT 3;
SELECT wm_acct_src_nb, wm_src_sys_cd FROM pcr.fpic_daily_adv_flows_tb_pm
WHERE wm_acct_src_nb IS NOT NULL LIMIT 3;
```
Wrap all sample values in pipes so padding is visible: |0000001590|

## F2 — Where do region and market come from?

`em_branch_no` (20,317) and `cwm_branch_cd` (4,943) are too granular. Find the real dimension.

```sql
-- F2a: any column anywhere in pcr that looks like a geography rollup
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='pcr'
  AND (column_name ILIKE '%region%' OR column_name ILIKE '%market%'
    OR column_name ILIKE '%hub%'    OR column_name ILIKE '%complex%'
    OR column_name ILIKE '%division%' OR column_name ILIKE '%territory%')
ORDER BY table_name, column_name
LIMIT 25;

-- F2b: is there a branch hierarchy / reference table?
SELECT table_name FROM information_schema.tables
WHERE table_schema='pcr'
  AND (table_name ILIKE '%branch%' OR table_name ILIKE '%region%'
    OR table_name ILIKE '%market%' OR table_name ILIKE '%hier%'
    OR table_name ILIKE '%org%')
LIMIT 20;

-- F2c: does the hub name on team agreements look like a market?
SELECT count(DISTINCT prm_hub_nme) AS hub_distinct FROM pcr.fpic_team_agreement_tb;
SELECT prm_hub_nme, count(*) FROM pcr.fpic_team_agreement_tb
GROUP BY 1 ORDER BY 2 DESC LIMIT 8;
```

## F3 — Coverage by month (filtered, not full scan)

```sql
-- trade: month must come from trade_dt, NOT proc_dt
SELECT to_char(trade_dt,'YYYY-MM') AS mth, count(*) AS rows
FROM pcr.fpic_daily_trade_details_tb_prod
WHERE trade_dt >= DATE '2026-04-01' AND trade_dt < DATE '2026-07-01'
GROUP BY 1 ORDER BY 1;

-- flows
SELECT to_char(bus_dt,'YYYY-MM') AS mth, count(*) AS rows
FROM pcr.fpic_daily_adv_flows_tb_pm
WHERE bus_dt >= DATE '2026-04-01' AND bus_dt < DATE '2026-07-01'
GROUP BY 1 ORDER BY 1;
```
If either still times out, report `FAILED` and instead run it for a single month only
(`WHERE trade_dt >= '2026-06-01' AND trade_dt < '2026-07-01'`) so I at least know whether June
exists.

## F4 — Flow JSONB keys (sampled)

```sql
SELECT DISTINCT jsonb_object_keys(other_attributes) AS k
FROM (SELECT other_attributes FROM pcr.fpic_daily_adv_flows_tb_pm
      WHERE other_attributes IS NOT NULL LIMIT 500) s
LIMIT 15;
```

---

## RETURN EXACTLY THIS

```
=== F1 ACCOUNT KEY JOIN ===
flow_sample:        found_in_trade:
found_in_rr:        found_in_eci_rel:
acct_tb_pm.account_number: | | | |
flows.wm_acct_src_nb:      | | | |   src_sys:

=== F2 REGION/MARKET ===
geo-like columns:  <table.column> | <type>
branch/org tables: <names>
hub_distinct:
top hub values:    <value> | <count>

=== F3 COVERAGE BY MONTH ===
trade 2026-04:      2026-05:      2026-06:
flows 2026-04:      2026-05:      2026-06:

=== F4 FLOW JSONB KEYS ===
<keys, comma separated>
```
