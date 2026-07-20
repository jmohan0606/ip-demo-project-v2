-- Source extraction (PostgreSQL). NOT executed by the app.
-- Verify advisor_sid on the trade table equals standard_id here; if not, fall back
-- to (prm_ofc_no, prm_rr_no). If names come back blank, display the advisor id —
-- do NOT invent names.
SELECT r.standard_id AS advisor_sid, r.rr_nam, r.prm_rr_no AS rep_code,
       r.cwm_branch_cd AS branch_cd, e.em_name_txt AS advisor_name
FROM   pcr.fpic_prm_rr_tb r
LEFT   JOIN pcr.fpic_employee_tb e ON e.em_standard_id = r.standard_id
WHERE  r.standard_id IN ('V236209','U869485','R452497','F074537','D194202',
                         'Z166924','I090694','V077477','I069872','U713250');
