-- Source extraction (PostgreSQL, schema pcr, db fpicdb UAT).
-- Run by a human; output dropped as CSV into data/real/. NOT executed by the app.
-- Credited revenue = post_split_credited_amt (pre_split × split_pct double-counts across advisors).
-- Month comes from trade_dt (proc_dt runs the day after month-end; year_month_no is 2% populated).
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
