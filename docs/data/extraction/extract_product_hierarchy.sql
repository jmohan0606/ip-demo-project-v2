-- Source extraction (PostgreSQL). grid_type='PRODUCT_TYPE' excludes
-- NON_CREDITED_REVENUE and PAY_TYPE_SUMMARY rows. NOT executed by the app.
SELECT DISTINCT product_code, sub_product_code,
       level_two_product, level_one_product,
       level_one_pay_type_product_cd, level_two_pay_type_product_cd
FROM   pcr.fpicdb_pcr_product_hierarchy
WHERE  grid_type = 'PRODUCT_TYPE';
