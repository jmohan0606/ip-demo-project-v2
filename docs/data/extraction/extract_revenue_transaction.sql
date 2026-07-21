-- GENERATED from docs/data/source_catalog.json by scripts/generate_extraction_sql.py
-- (do not edit by hand — edit the catalog and regenerate).
-- Source extraction (PostgreSQL, schema pcr, db fpicdb). Run by a human;
-- output dropped as CSV into data/real/. NOT executed by the app — shown in
-- the evidence modal for lineage and independent verification only.
-- Credited revenue = post_split_credited_amt (pre_split x split_pct double-counts across advisors).
-- Month comes from trade_dt (proc_dt runs the day after month-end; year_month_no is 2% populated).
-- R1-5: reason_cd / rm_sid / cs_sid / grid_type are PULLED AS COLUMNS. The grid_type
-- filter was deliberately REMOVED from the WHERE: eligibility (reason codes, grid
-- types, the 90-day rule) is applied by the application from phx_dm_v2_reason_code
-- data + config, never baked into the extract.
SELECT d.trade_ref_no, d.split_seq_no, d.advisor_sid,
       to_char(d.trade_dt,'YYYYMM')          AS month_id,
       d.product_cd, d.product_sub_cd, d.account_no,
       d.trade_dt, d.proc_dt,
       d.post_split_credited_amt, d.pre_split_credited_amt, d.split_pct,
       d.client_rate_bps, d.std_tier_rate,
       d.concession_type, d.discount_amt, d.eff_disc_pct,
       d.avg_balance_amt, d.file_key, d.trade_description,
       d.reason_cd, d.rm_sid, d.cs_sid,
       h.grid_type
FROM   pcr.fpic_daily_trade_details_tb_prod d
JOIN   pcr.product_hierarchy h
       ON  d.product_cd     = h.product_code
       AND d.product_sub_cd = h.sub_product_code
WHERE  d.trade_dt >= DATE '2026-04-01'
  AND  d.trade_dt <  DATE '2026-07-01'
  AND  d.advisor_sid IN ('V236209','U869485','R452497','F074537','D194202',
                         'Z166924','I090694','V077477','I069872','U713250');
