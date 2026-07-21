-- GENERATED from docs/data/source_catalog.json by scripts/generate_extraction_sql.py
-- (do not edit by hand — edit the catalog and regenerate).
-- Source extraction (PostgreSQL, schema pcr, db fpicdb). Run by a human;
-- output dropped as CSV into data/real/. NOT executed by the app — shown in
-- the evidence modal for lineage and independent verification only.
-- Verify advisor_sid on the trade table equals standard_id here; if not, fall
-- back to (prm_ofc_no, prm_rr_no). Blank names -> display the advisor id; never
-- invent names.
SELECT r.standard_id AS advisor_sid, r.rr_nam, r.prm_rr_no AS rep_code,
       r.cwm_branch_cd AS branch_cd, e.em_name_txt AS advisor_name
FROM   pcr.fpic_prm_rr_tb r
LEFT   JOIN pcr.fpic_employee_tb e ON e.em_standard_id = r.standard_id
WHERE  r.standard_id IN ('V236209','U869485','R452497','F074537','D194202',
                        'Z166924','I090694','V077477','I069872','U713250');
