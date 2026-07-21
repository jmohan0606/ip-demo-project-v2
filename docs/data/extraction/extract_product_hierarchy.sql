-- GENERATED from docs/data/source_catalog.json by scripts/generate_extraction_sql.py
-- (do not edit by hand — edit the catalog and regenerate).
-- Source extraction (PostgreSQL, schema pcr, db fpicdb). Run by a human;
-- output dropped as CSV into data/real/. NOT executed by the app — shown in
-- the evidence modal for lineage and independent verification only.
-- R1-4: grid_type is pulled as a COLUMN (PRODUCT_TYPE | NON_CREDITED_REVENUE |
-- PAY_TYPE_SUMMARY), no longer filtered here. The revenue computation filters on
-- CREDITED_GRID_TYPES config, so relaxing the filter needs no re-extract.
SELECT DISTINCT product_code, sub_product_code,
       level_two_product, level_one_product, grid_type,
       level_one_pay_type_product_cd, level_two_pay_type_product_cd
FROM   pcr.product_hierarchy;
