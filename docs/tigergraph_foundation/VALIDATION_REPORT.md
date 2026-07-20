# Validation Report — Story 1 Rebuild v0.2.0

## Result summary

| Validation area | Status | Evidence |
|---|---|---|
| Schema/manifest/CSV consistency | PASS | `reports/static_validation_report.md` |
| GSQL semantic/static review | PASS | `reports/query_audit.md` and validator output |
| Server-side loading-job audit | PASS | `reports/loading_job_audit.md` |
| Query-case data and authorization preconditions | PASS | `reports/query_case_data_validation.md` |
| Business scenario coverage | PASS | `reports/business_scenario_validation.md` |
| FastAPI tests | PASS | `make validate` console output |
| Python compilation | PASS | `make validate` console output |
| React production build | PASS | `make validate` console output |
| Full mock ingestion | PASS | `reports/full_mock_ingestion.md` |
| Clean release/debris/secret/version audit | PASS | `reports/release_audit.md` |
| Live TigerGraph schema/query compile | PENDING | Requires target TigerGraph 4.2.2 |
| Live RESTPP ingestion/cardinality | PENDING | Requires target TigerGraph 4.2.2 |
| Live execution of 43 query cases | PENDING | Requires target TigerGraph 4.2.2 |

## Static package totals

- 56 vertices
- 126 directed edges
- 126 explicit reverse edges
- 182 CSV targets
- 109,328 source rows
- 182 loading jobs
- 43 query implementations
- 43 query cases
- 48 business-scenario checks

## What the mock ingestion proves

The full mock run verifies:

- Dependency-ordered processing of every manifest entry.
- Batch/checkpoint creation.
- Exact success/failure accounting.
- SQLite run/file/batch/error tracking.
- Completion at 100 percent with zero row errors.
- Hash-based skipping of all unchanged rows on the second run.

It does not prove GSQL compiler compatibility or live RESTPP data acceptance.

## Mandatory release gate

The package must not be promoted as TigerGraph-validated until `make live-install` and `make live-validate` succeed against the actual TigerGraph 4.2.2 instance and the generated live validation report shows PASS for cardinality and all 43 query cases.
