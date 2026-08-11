Run these three checks against `pcr` in `fpicdb` and return ONLY the filled template at the bottom.

## OUTPUT RULES

1. Output ONLY the filled template. No preamble, no plan, no checklist, no summary, no offers to
   do more. This is being photographed — keep it under 20 lines.
2. If a query fails, write `FAILED: <one-line reason>`. Do NOT substitute a different query,
   do NOT estimate, do NOT infer an answer from table names or row counts you saw earlier.
3. If a table or column does not exist, write `NO SUCH TABLE` / `NO SUCH COLUMN` — do not silently
   swap in a similar one.
4. Every number must come from a query you actually executed in this session. If you did not run
   it, write `NOT RUN`.
5. Report dates in `YYYY-MM-DD` format.

Raise the timeout first:
```sql
SET statement_timeout = '600s';
```

---

## G1 — Is June 2026 trade data complete or cut off mid-month?

```sql
SELECT min(trade_dt) AS june_min,
       max(trade_dt) AS june_max,
       count(DISTINCT trade_dt) AS distinct_days
FROM pcr.fpic_daily_trade_details_tb_prod
WHERE trade_dt >= DATE '2026-06-01' AND trade_dt < DATE '2026-07-01';
```

For comparison, the same for May (a known-complete month):
```sql
SELECT min(trade_dt) AS may_min,
       max(trade_dt) AS may_max,
       count(DISTINCT trade_dt) AS distinct_days
FROM pcr.fpic_daily_trade_details_tb_prod
WHERE trade_dt >= DATE '2026-05-01' AND trade_dt < DATE '2026-06-01';
```

## G2 — Do advisor flows join to `_tb_prod` or to `_tb`?

IMPORTANT: use a RANDOM sample. A plain `LIMIT 100` returns one contiguous feed batch and gives a
misleading answer — that is what happened on the previous run.

```sql
WITH f AS (
  SELECT DISTINCT ltrim(trim(wm_acct_src_nb),'0') AS k
  FROM pcr.fpic_daily_adv_flows_tb_pm
  WHERE wm_acct_src_nb IS NOT NULL
    AND ltrim(trim(wm_acct_src_nb),'0') <> ''
  ORDER BY random()
  LIMIT 100
)
SELECT
  count(*) AS sample_size,
  count(*) FILTER (WHERE EXISTS (
    SELECT 1 FROM pcr.fpic_daily_trade_details_tb_prod t
    WHERE ltrim(trim(t.account_no),'0') = f.k)) AS in_prod,
  count(*) FILTER (WHERE EXISTS (
    SELECT 1 FROM pcr.fpic_daily_trade_details_tb t
    WHERE ltrim(trim(t.account_no),'0') = f.k)) AS in_nonprod
FROM f;
```

If that times out, run the two halves separately (one `EXISTS` per query) and report each.

If BOTH come back 0, run this fallback to check whether the flow account key needs a different
normalisation rather than zero-stripping:
```sql
SELECT f.wm_acct_src_nb, f.wm_src_sys_cd, t.account_no
FROM (SELECT DISTINCT wm_acct_src_nb, wm_src_sys_cd
      FROM pcr.fpic_daily_adv_flows_tb_pm ORDER BY random() LIMIT 5) f
LEFT JOIN LATERAL (
  SELECT account_no FROM pcr.fpic_daily_trade_details_tb_prod
  WHERE right(ltrim(trim(account_no),'0'), 6) = right(ltrim(trim(f.wm_acct_src_nb),'0'), 6)
  LIMIT 1) t ON true;
```
Report those 5 rows raw, pipe-wrapped like |76001570|.

## G3 — Which trade table is the current one?

```sql
SELECT max(trade_dt) AS prod_max, count(*) AS prod_rows
FROM pcr.fpic_daily_trade_details_tb_prod;

SELECT max(trade_dt) AS nonprod_max, count(*) AS nonprod_rows
FROM pcr.fpic_daily_trade_details_tb;
```
If the `count(*)` times out, drop it and report only the max date.

Also report distinct source-system codes on the flow side, since every sampled row showed `SCPP`:
```sql
SELECT wm_src_sys_cd, count(*) FROM pcr.fpic_daily_adv_flows_tb_pm
GROUP BY 1 ORDER BY 2 DESC LIMIT 5;
```

---

## RETURN EXACTLY THIS — nothing else

```
=== G1 JUNE COMPLETENESS ===
june_min:        june_max:        distinct_days:
may_min:         may_max:         distinct_days:

=== G2 FLOW JOIN ===
sample_size:     in_prod:         in_nonprod:
(fallback rows only if both were 0):
  |flow_acct| |src_sys| |trade_acct|

=== G3 TABLE CURRENCY ===
prod_max:        prod_rows:
nonprod_max:     nonprod_rows:
flow src_sys values: <code> | <count>
```
