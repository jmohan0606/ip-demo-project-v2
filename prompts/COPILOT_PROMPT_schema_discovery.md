I need you to run five short investigations against the `pcr` schema in `fpicdb` and report back
in a FIXED format. This output is going to be photographed and read by someone else, so follow the
output rules exactly.

## OUTPUT RULES — these matter more than completeness

1. Output ONLY the filled-in template at the bottom. No preamble, no "Great — here's what I found",
   no plan/checklist, no summary, no next-step offers.
2. Keep the whole output under 60 lines so it fits in one screenshot.
3. If a query fails, write `FAILED: <one-line reason>` on that line. Do NOT substitute a different
   query, do NOT estimate, do NOT infer the answer from table/column names.
4. If a column I reference does not exist, write `NO SUCH COLUMN: <name>` and list the closest
   actual column names. Do not silently swap in a similar column.
5. Every number must come from a query you actually executed. If you did not run it, write `NOT RUN`.
6. Do not truncate or prettify sample values. I need the RAW strings including any leading zeros,
   spaces or prefixes. Wrap them in pipes like |000123456| so padding is visible.

---

## Q1 — Do trade accounts and flow accounts join? (most important)

```sql
-- Q1a raw equality
SELECT count(*) AS matched_raw
FROM pcr.fpic_daily_trade_details_tb_prod t
JOIN pcr.fpic_daily_adv_flows_tb_pm f
  ON t.account_no = f.wm_acct_src_nb;

-- Q1b normalised equality (trim + strip leading zeros)
SELECT count(*) AS matched_norm
FROM pcr.fpic_daily_trade_details_tb_prod t
JOIN pcr.fpic_daily_adv_flows_tb_pm f
  ON ltrim(trim(t.account_no),'0') = ltrim(trim(f.wm_acct_src_nb),'0');

-- Q1c raw sample values from each account-key column
SELECT DISTINCT account_no      FROM pcr.fpic_daily_trade_details_tb_prod LIMIT 3;
SELECT DISTINCT account_number  FROM pcr.fpic_acct_tb_pm                  LIMIT 3;
SELECT DISTINCT account_no      FROM pcr.fpic_rr_changes_from_nacs_logs   LIMIT 3;
SELECT DISTINCT wm_acct_src_nb, wm_src_sys_cd FROM pcr.fpic_daily_adv_flows_tb_pm LIMIT 3;
SELECT DISTINCT account_number, party_eci_id  FROM pcr.fpic_acct_eci_rel_tb_pm    LIMIT 3;
SELECT DISTINCT wm_acct_src_nb, eci_nb        FROM pcr.fpic_acct_eci_map_tb       LIMIT 3;

-- Q1d does ANY table carry both key families? (answer yes/no + table names)
SELECT table_name, string_agg(column_name, ', ' ORDER BY column_name) AS cols
FROM information_schema.columns
WHERE table_schema='pcr'
  AND column_name IN ('account_no','account_number','wm_acct_src_nb','acct_id')
GROUP BY table_name
HAVING count(DISTINCT column_name) > 1
LIMIT 10;
```

## Q2 — Region and market columns

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='pcr'
  AND table_name IN ('fpic_prm_rr_tb','fpic_employee_tb')
  AND (column_name ILIKE '%region%' OR column_name ILIKE '%market%'
    OR column_name ILIKE '%branch%'  OR column_name ILIKE '%div%'
    OR column_name ILIKE '%terr%'    OR column_name ILIKE '%zone%'
    OR column_name ILIKE '%area%'    OR column_name ILIKE '%complex%'
    OR column_name ILIKE '%hub%'     OR column_name ILIKE '%office%')
ORDER BY table_name, column_name;
```
Then for EACH column returned, report `count(DISTINCT <col>)` from its table. I need to know which
columns have a sensible cardinality (roughly 5–60 distinct values) to serve as region/market.

## Q3 — Is the team split already in post_split_credited_amt?

```sql
SELECT t.account_no, t.advisor_sid,
       t.pre_split_credited_amt, t.split_pct, t.post_split_credited_amt,
       a.prm_standard_id, a.prm_share_pct, a.sec_standard_id, a.sec_share_pct,
       a.team_agreement_status_cd
FROM pcr.fpic_daily_trade_details_tb_prod t
JOIN pcr.fpic_team_agreement_tb a
  ON t.advisor_sid = a.prm_standard_id
 AND t.trade_dt >= a.start_ts::date AND t.trade_dt < a.end_ts::date
WHERE t.trade_dt >= DATE '2026-04-01' AND t.trade_dt < DATE '2026-07-01'
LIMIT 5;
```
Report the 5 rows. Then answer this ONE question with YES / NO / CANNOT TELL:
**does `split_pct` equal `prm_share_pct` (or `sec_share_pct`) on these rows?**

Also: `SELECT min(prm_share_pct), max(prm_share_pct) FROM pcr.fpic_team_agreement_tb;`
(I need to know whether 60% is stored as 60.0000000 or 0.6000000.)

## Q4 — Product hierarchy shape

```sql
SELECT count(DISTINCT level_one_product) AS lvl1_distinct,
       count(DISTINCT level_two_product) AS lvl2_distinct,
       count(DISTINCT product_code)      AS prod_distinct,
       count(DISTINCT grid_type)         AS grid_types
FROM pcr.product_hierarchy;

SELECT DISTINCT grid_type FROM pcr.product_hierarchy ORDER BY 1;
```

## Q5 — Small facts

```sql
-- date format
SELECT account_open_dt, count(*) FROM pcr.fpic_acct_tb_pm
GROUP BY 1 ORDER BY 2 DESC LIMIT 3;

-- intra-team vs real advisor transfers
SELECT count(*) FILTER (WHERE from_rr =  to_rr) AS intra_team,
       count(*) FILTER (WHERE from_rr <> to_rr) AS between_advisors
FROM pcr.fpic_rr_changes_from_nacs_logs
WHERE transfer_ts >= DATE '2026-04-01' AND transfer_ts < DATE '2026-07-01';

-- household roles
SELECT enterprise_relationship_code, party_role_name, count(*)
FROM pcr.fpic_acct_eci_rel_tb_pm GROUP BY 1,2 ORDER BY 3 DESC LIMIT 5;

-- flow jsonb keys
SELECT jsonb_object_keys(other_attributes) AS k, count(*)
FROM pcr.fpic_daily_adv_flows_tb_pm GROUP BY 1 ORDER BY 2 DESC LIMIT 8;

-- flow coverage by month
SELECT to_char(bus_dt,'YYYY-MM') AS mth, count(*) FROM pcr.fpic_daily_adv_flows_tb_pm
GROUP BY 1 ORDER BY 1;

-- trade coverage by month, on trade_dt NOT proc_dt
SELECT to_char(trade_dt,'YYYY-MM') AS mth, count(*)
FROM pcr.fpic_daily_trade_details_tb_prod
WHERE trade_dt >= DATE '2026-04-01' AND trade_dt < DATE '2026-07-01'
GROUP BY 1 ORDER BY 1;
```

---

## FILL IN AND RETURN EXACTLY THIS — nothing else

```
=== Q1 ACCOUNT KEYS ===
matched_raw:
matched_norm:
trade.account_no:        | | | |
acct_tb_pm.account_number:| | | |
rr_changes.account_no:   | | | |
flows.wm_acct_src_nb:    | | | |   src_sys:
eci_rel.account_number:  | | | |   party_eci_id: | |
eci_map.wm_acct_src_nb:  | | | |   eci_nb:       | |
tables carrying both key families:

=== Q2 REGION/MARKET ===
<table.column> | <data_type> | <distinct count>
(one line per candidate column)

=== Q3 TEAM SPLIT ===
(5 rows, pipe-separated)
split_pct == share_pct?  YES / NO / CANNOT TELL
prm_share_pct min / max:

=== Q4 PRODUCT HIERARCHY ===
lvl1_distinct:   lvl2_distinct:   prod_distinct:   grid_types:
grid_type values:

=== Q5 SMALL FACTS ===
account_open_dt samples:  | | | |
intra_team:        between_advisors:
household roles (top 5): <rel_code> | <role_name> | <count>
flow jsonb keys:
flow rows by month:
trade rows by month (trade_dt):
```
