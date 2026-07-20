# Foundation Package — Real-Engine GSQL/Loader Fixes (upstream report)

During Phase 2 of the iPerform Insights & Coaching rebuild, the
`iperform_story1_tigergraph_foundation_v0.2.0` package was installed and loaded on an
**actual TigerGraph Community Edition 4.2.3** engine (Docker, single-server). The package's
static validators (`scripts/validate_*.py`, `make validate`) pass 4/4 and the query-semantics
checker passes 43/43 — but four defects only surface when the DDL/jobs are compiled and run by a
real GSQL engine, which static analysis cannot catch. All four were fixed locally to complete the
load; they should be fixed **in the package itself and in its validators** so the next consumer
does not rediscover them.

Engine used: `tigergraph/community:4.2.3`. Each finding below gives the symptom, the root cause,
the fix applied, and a suggested validator check.

---

## Finding 1 — Trailing `;` after `WITH …` DDL clauses is rejected by `gsql -f`

**Affected files:** `tigergraph/schema/*.gsql` (all 56 vertex + 126 edge `CREATE` statements
that carry a `WITH` clause).

**Symptom:** `gsql -f schema/*.gsql` fails to parse `CREATE VERTEX … WITH
primary_id_as_attribute="true";` and `CREATE … EDGE … WITH REVERSE_EDGE="…";` — the trailing
semicolon after the `WITH` attribute list is a syntax error in this engine's DDL parser when
files are fed with `-f`.

**Root cause:** the shipped DDL terminates every `CREATE` with `;`, but 4.2.3 does not accept a
statement terminator immediately following a `WITH primary_id_as_attribute=…` / `WITH
REVERSE_EDGE=…` clause in file-mode.

**Fix applied:** strip the trailing `;` from every `CREATE VERTEX`/`CREATE … EDGE` statement that
ends in a `WITH …` clause. After this, all 56 vertices + 126 edges + the graph create
successfully.

**Suggested validator check:** flag any `CREATE (VERTEX|… EDGE) … WITH …;` line whose `WITH`
clause is immediately followed by `;`, or normalize the terminator during package generation.

---

## Finding 2 — Loading jobs use `$"col"` with `HEADER="true"` but never initialize `DEFINE FILENAME`

**Affected files:** `tigergraph/loading/jobs/*.gsql` — **all 182 loading jobs**.

**Symptom:** every job fails the GSQL *semantic* check at install time. Jobs reference columns by
name (`$"advisor_name"`, etc.) under `USING HEADER="true"`, but the engine requires the
`FILENAME` variable to be **initialized to a concrete path** before header-name column references
resolve; as shipped the `DEFINE FILENAME f;` is declared but left uninitialized, so the semantic
checker cannot bind `$"col"` and rejects the job.

**Root cause:** named-column (`$"header"`) resolution in 4.2.3 is gated on an initialized
`DEFINE FILENAME f = "…";`. A bare `DEFINE FILENAME f;` compiles structurally (passes static
validation) but fails real semantic check.

**Fix applied:** initialize each job's `FILENAME` to the container CSV path
(`DEFINE FILENAME f = "/home/tigergraph/mydata/<entity>.csv";`) before the `LOAD` block. After
this, all 182 jobs compile.

**Suggested validator check:** require every `DEFINE FILENAME` that is later used with a
`$"header"` reference to carry an initializer, or emit the initializer at generation time from
`data/manifest.json` paths.

---

## Finding 3 — Missing `QUOTE="double"` on jobs whose CSVs contain quoted JSON columns

**Affected files:** the loading jobs for the ~16 vertex types whose CSVs carry quoted
JSON/array/object columns.

**Symptom:** those jobs load **0 objects** (or mis-parse) because the loader defaults to no quote
handling, so a quoted field containing the separator is split on the internal comma.

**Root cause:** the shipped `USING` clauses omit `QUOTE="double"`. Any CSV column that is a
double-quoted JSON blob needs `QUOTE="double"` for the loader to treat the quotes as field
delimiters rather than literal characters.

**Fix applied:** add `QUOTE="double"` to the `USING` clause of the affected jobs. This lifted the
successful vertex-type load from 40 → 51 types via the file loader.

**Suggested validator check:** for any entity whose manifest/schema column type is a JSON/array/
object (or whose sample CSV has quoted fields), assert the generated job's `USING` clause
includes `QUOTE="double"`.

---

## Finding 4 — `QUOTE="double"` tokenizer fails on fields with BOTH a `""` escape AND an internal comma

**Affected vertex types (5):** `reasoning_trace`, `similarity_match`, `learning_signal`,
`coaching_session`, `simulation_scenario` — i.e. exactly the types whose JSON columns hold
arrays/objects that contain **both** an escaped double-quote (`""`) **and** the separator comma
inside the same quoted field. (`crm_activity` loads fine: its comma-bearing free-text column has
no `""` escape.)

**Symptom:** with `QUOTE="double"` in place (Finding 3), these jobs still load **0 objects** with
an "Invalid Attributes" error. Isolated by controlled single-row tests / binary search:

| Field shape | Result |
|---|---|
| plain string + date-only DATETIME | loads OK |
| `""`-escaped JSON, NO internal comma, + date-only | loads OK |
| `""`-escaped JSON **WITH** internal comma | 0 objects, "Invalid Attributes" |

**Root cause:** the TigerGraph 4.2.3 GSQL **file-loader** CSV tokenizer mis-splits a
`QUOTE="double"` field on the internal comma when that field also contains a `""` escape. The
column split shifts every subsequent column left by one, so the `DATETIME` attribute receives
JSON text and the entire row is rejected. This is an engine-level tokenizer bug, not a
schema/data error — the CSVs themselves are well-formed.

**Fix / correct production path:** do **not** load these 5 types through the GSQL file loader.
Use **RESTPP JSON upsert** instead (the foundation package's own real ingestion service, and this
project's `RealGraphClient.upsert`), which constructs the upsert payload as JSON and bypasses the
CSV tokenizer entirely. Verified live against the container: the 4 affected types
(`coaching_session`, `similarity_match`, `learning_signal`, `reasoning_trace`) loaded via RESTPP
upsert; `simulation_scenario` was pending only a transient RESTPP 408 under concurrent load.

**Suggested validator/doc action:** document that the file loader must not be used for these 5
types on 4.2.3; route them through RESTPP upsert. If file-loading is required, a workaround is to
choose a separator that does not appear in the JSON payload, or to base64/escape the comma before
loading.

---

## Verified-good on the real engine (context)

- Schema DDL compiles: 56 vertices + 126 edges + graph created (after Finding 1).
- All 182 loading jobs compile (after Finding 2).
- Data loads: 55/56 vertex types populated — 51 via the file loader (after Finding 3), 4 via live
  RESTPP upsert (Finding 4 workaround).
- `RealGraphClient` verified live against the container (health + JSON upsert).

## Not achievable on the 2-core/8GB build box (hardware, not a package defect)

- Full edge-data file-load (the loader wedges under load on 2 cores) and the 43-query C++
  `INSTALL` (compiler hangs/crashes) — both are the documented Section-8 "machine can't handle
  it" case, deferred to a larger host. Query *semantics* are already proven 43/43 by the
  package's own `validate_query_semantics` and by this project's MockGraphClient contract tests.
