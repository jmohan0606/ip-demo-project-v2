# iPerform Insights & Coaching — Story 1 TigerGraph Foundation v0.2.0

This package is the rebuilt, acceptance-gated TigerGraph foundation for the iPerform Insights & Coaching application. It provides the graph schema, deterministic showcase data, server-side loading jobs, substantive GSQL analytics and retrieval queries, a FastAPI RESTPP ingestion service, SQLite operational tracking, and a React/MUI Data Management console.

## Release status

**Local/static implementation status: PASS**  
**Full mock ingestion status: PASS**  
**Live TigerGraph 4.2.2 installation and execution status: PENDING TARGET ENVIRONMENT**

The package has been checked locally for schema/data/query consistency, Python behavior, React compilation, loader orchestration, resumability, unchanged-file detection, and business-scenario coverage. It has not been compiled or executed against the customer's live TigerGraph 4.2.2 instance because that environment and credentials are not available in this workspace. Do not interpret mock mode as proof of live TigerGraph compatibility; follow `docs/live_tigergraph_runbook.md` to complete that gate.

## Authoritative baseline

The historical uploaded GSQL files were no longer available in the active workspace during this rebuild. This release therefore creates a new consolidated Story 1 schema from the approved v1.1 requirements, the previously confirmed logical inventory, and the required hierarchy/AGP/CRM/AI extensions. It is not represented as a byte-for-byte modification of the unavailable historical files.

## Package inventory

- Graph: `iperform_insights_coaching_demo`
- Vertex types: **56**
- Directed edge types: **126**
- Explicit reverse edges: **126**
- Manifest-controlled CSV targets: **182**
- Deterministic sample rows: **109,328**
- Server-side GSQL loading jobs: **182**
- Implemented GSQL query files: **43**
- Deterministic query test cases: **43**
- Validated business-scenario checks: **48**

## Business coverage

The sample graph supports the planned application screens and agentic-AI demonstrations:

- Firm → Division → Region → Market → Branch → Advisor organization hierarchy.
- DDW → RDW → MDW → Advisor management hierarchy.
- Executive, DDW, RDW, MDW, Advisor, AGP Advisor, Compliance, Admin and AI Ops personas.
- Advisor, Household, Account, Product, transaction and monthly revenue/AUM/NCF/NNM relationships.
- A 24-month AGP program with milestones at months 3, 6, 9, 12, 15, 18, 21 and 24.
- AGP goals, KPIs, milestone measurements, coaching and manager reviews.
- CRM activities, leads, referrals and CRM opportunities with pending/completed/overdue/converted/won/lost variations.
- Deterministic feature snapshots, embeddings, similarity matches and prediction results.
- AI-discovered opportunities and recommendations with Info, Attention, Urgent and Critical severity.
- Context memory, conversation turns, reasoning traces, evidence lineage, feedback, outcomes and learning signals.
- Documents, chunks, playbooks, best practices, glossary, notifications, agent executions, tool calls, evaluations and guardrail events.

## Architecture

```text
React/MUI Data Management Console
              |
              v
FastAPI catalog, ingestion and validation APIs
              |
       +------+--------------------+
       |                           |
       v                           v
SQLite operational tracker    TigerGraph RESTPP
(runs/files/batches/errors/    (business graph,
 hashes/checkpoints/results)    installed GSQL queries)
       ^                           ^
       |                           |
       +---- manifest + CSV -------+
```

React never receives TigerGraph credentials. SQLite stores ingestion operations only; TigerGraph remains the business-data system of record.

## Repository structure

- `tigergraph/schema/` — consolidated vertex, edge and graph definitions.
- `tigergraph/loading/` — 182 server-side GSQL loading jobs and install bundle.
- `tigergraph/queries/` — 43 substantive queries, query catalog and install bundle.
- `data/sample/` — deterministic CSV source data.
- `data/manifest.json` — authoritative CSV mapping, load order, dependencies and expected counts.
- `backend/` — FastAPI, RESTPP client, SQLite tracking and ingestion orchestration.
- `frontend/` — React/TypeScript/MUI loader and validation console.
- `tests/query_cases.json` — one deterministic invocation contract per GSQL query.
- `scripts/` — static validation, business checks, full mock load and live TigerGraph validation.
- `reports/` — generated evidence from validation runs.
- `docs/` — architecture, data scenarios, limitations and live installation runbook.

## Local prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- npm
- Access to TigerGraph GSQL and RESTPP only for live installation/validation

## Install dependencies

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Frontend

```bash
cd frontend
npm ci
```

## Run the complete local acceptance suite

From the package root:

```bash
make validate
```

This performs:

1. Schema, manifest, CSV and test-case validation.
2. GSQL traversal/attribute/direction semantic review.
3. Query parameter and implementation audit.
4. Query-case IDs, enum values, date ranges and persona authorization precondition validation.
5. Loading-job-to-schema/manifest audit.
6. Business-scenario coverage validation.
7. Source marker scan.
8. FastAPI unit/API tests and Python compilation.
9. React production build.
10. A complete 182-file mock ingestion.
11. A second unchanged-file run proving hash-based skipping.

Mock mode validates application orchestration and SQLite tracking only. It does not install or execute GSQL on TigerGraph.

## Start the application in explicit mock mode

### Backend

```bash
cd backend
cp .env.mock.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. The UI visibly labels the backend as **mock**.

## Connect to live TigerGraph

1. Copy the live environment template:

```bash
cd backend
cp .env.example .env
```

2. Configure:

```dotenv
MOCK_TIGERGRAPH=false
GRAPH_NAME=iperform_insights_coaching_demo
TIGERGRAPH_RESTPP_URL=https://<host>:14240/restpp
TIGERGRAPH_TOKEN=<token>
TIGERGRAPH_VERIFY_SSL=true
```

3. Install schema, server-side loading jobs and queries using the GSQL client:

```bash
export GSQL_CMD=gsql
make live-install
```

4. Start FastAPI and use the React UI to validate and load the manifest-controlled CSV files through RESTPP.

5. Execute live cardinality and all-query validation:

```bash
export TIGERGRAPH_RESTPP_URL=https://<host>:14240/restpp
export TIGERGRAPH_TOKEN=<token>
make live-validate
```

See `docs/live_tigergraph_runbook.md` for the mandatory step-by-step gate and troubleshooting guidance.

## Data Management UI capabilities

The React console provides:

- Manifest/file discovery and dependency visualization.
- Validate selected files or the complete package.
- Load selected targets or all targets in dependency order.
- Configurable batch size and unchanged-file skipping.
- Pause, resume and retry-failed operations.
- Per-run/file/batch progress and row-level error review.
- TigerGraph vertex/edge cardinality validation.
- Execution of all 43 installed query test cases.
- Query catalog and run history.
- Visible live/mock mode and live-validation status.

## GSQL implementation status

All 43 query files contain substantive traversal, filtering, aggregation or retrieval logic and have deterministic test cases. Static validation verifies declared parameters, schema attributes, edge direction, accumulator use, test-case coverage and delimiters. The query catalog intentionally records `implemented-static-reviewed-live-compile-pending` until the live TigerGraph gate is executed.

## Safety decisions

- Mock mode is opt-in; live mode is the default configuration.
- No graph delete/reset action is exposed in the UI.
- TigerGraph credentials remain server-side.
- Edge upserts require endpoint vertices to exist.
- Exact accepted-row counts are enforced.
- Batch failures are isolated recursively and persisted for retry.
- File hashes and checkpoints support resumable/idempotent ingestion.

## Release evidence

- `VALIDATION_REPORT.md`
- `PACKAGE_STATUS.md`
- `reports/static_validation_report.md`
- `reports/query_audit.md`
- `reports/loading_job_audit.md`
- `reports/query_case_data_validation.md`
- `reports/business_scenario_validation.md`
- `reports/full_mock_ingestion.md`
- `reports/release_audit.md`

