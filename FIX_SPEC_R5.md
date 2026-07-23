# FIX SPEC — iPerform V2, Round 5 · INGESTION RESCUE

> **Read completely before starting.** Supersedes CLAUDE.md / FIX_SPEC / R3 / R4 where they
> conflict. CLAUDE.md §0 (autonomous), §0.1 (PROGRESS), §3 (absolute rules) and rule 8a still
> apply.
>
> **Context you must understand before writing code:** rounds 1–4 verified everything on the
> **local SQLite tier only**. The first real load against live TigerGraph exposed that the
> ingestion path is fundamentally unreliable: it reports success while writing nothing,
> silently drops every attribute, and its delete/reset paths throw 500s. **Nothing else in
> this round matters until ingestion is trustworthy.**
>
> **New standing rule: REAL DATA ONLY.** Sample data is for automated tests only. Every
> demo, screenshot and verification in this round must use `DATA_SET=real`. Do not "verify"
> anything by falling back to sample.

---

## 0. WORKING AGREEMENT

Autonomous, auto mode, no checkpoints, no questions. Append the W-prefixed tasks from §W12
to `PROGRESS.md`. Commit granularly; push after each work-stream. **Work-stream A must be
completed and verified before B.** Add a "Round 5" section to `BUILD_REPORT.md`.

**Verification rule for this round:** a task is only DONE when verified against **actual
graph contents**, never against the ingestion screen's own reporting. The screen has been
lying; do not trust it as evidence.

---

# WORK-STREAM A — INGESTION CORRECTNESS (nothing else until this is right)

Seven confirmed defects, each traced to a file and line.

## A1 — Attributes silently dropped; only the primary key is written

**Traced:** `app/graph/tiered_client.py:53` `_entry_attributes()`
```python
for source_column, graph_attribute in entry.get("columns", {}).items():
    value = row.get(source_column)
    if value in ("", None):
        continue                      # ← silent skip
    attributes[graph_attribute] = _coerce(value)
```
If a manifest column name does not exactly match the CSV header, `row.get()` returns `None`
and the attribute is skipped **without any error**. Every attribute drops → TigerGraph
creates a vertex holding only its ID → the batch still reports success. This is the primary
cause of "it loaded but the row is empty".

**Fix:**
1. **Pre-flight column validation.** Before loading any entity, compare the CSV header set
   against the manifest `columns` keys. On mismatch, **fail that entity immediately** with a
   precise error naming the missing/extra columns. Never proceed with a partial mapping.
2. **Distinguish "absent" from "empty".** `row.get(col)` returning `None` (column absent)
   is an **error**; a present-but-empty value is legitimately skippable. Today both are
   silently skipped — separate them.
3. **Assert attribute count.** After building `attributes`, if a vertex ends up with **zero**
   attributes while its manifest declares more than the id column, raise — never write an
   attribute-less vertex.
4. Apply the identical fix to the edge path.

## A2 — CSV quoting breaks column alignment

Values containing commas (e.g. an advisor name `"Alvarez, Katherine"`) are written quoted,
but some read paths — notably **manual file upload** — split naively on commas, shifting
every subsequent value one column left. Observed: the name landed in the wrong column.

**Fix:** every CSV read and write path must use the `csv` module with proper quoting
(`csv.DictReader` / `csv.DictWriter`, `quoting=csv.QUOTE_MINIMAL`), never manual `split(",")`.
Audit **all** read paths: `ingestion_service.py:93,170`, the manual-upload endpoint, and any
frontend-side parsing. Add a regression test with a value containing a comma, a quote, and a
newline.

## A3 — CSV written with CRLF on every platform

**Traced:** `app/v2/dataset/builder.py:91`
```python
with path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
```
`csv.DictWriter`'s default `lineterminator` is `\r\n`, so with `newline=""` the file gets
CRLF regardless of OS.

**Fix:** `csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")`.
Apply everywhere CSVs are written. Also make readers BOM-tolerant (`encoding="utf-8-sig"`)
so a BOM can never corrupt the first header.

## A4 — Checkpoint records success without verifying the write

**Traced:** `app/ingestion/ingestion_service.py` writes the batch record and row hashes after
*processing* rows, not after TigerGraph *confirms* them. Result observed today:
`phx_dm_ingestion_batch` shows `created=2, processed=2, 100% completed` while the graph holds
**0 rows**. Every subsequent reload then hash-matches and skips as "Unchanged", making the
failure permanent and invisible.

**Fix:**
1. Write row hashes and the batch success record **only after** a confirmed successful
   upsert response for that batch. On any failure or partial acceptance, record the batch as
   `FAILED` with the error and **do not** write hashes.
2. `PartialUpsertError` already exists in `tiered_client.py` — ensure it propagates and marks
   the batch failed rather than being swallowed.
3. **Reconcile on read:** when reporting status, if the checkpoint claims rows loaded but the
   graph count is lower, report the discrepancy loudly (see A5/B4).

## A5 — Screen state comes from the checkpoint, not the graph

**Traced:** the screen's loaded state comes from `GET /ingestion/batches` →
`phx_dm_ingestion_batch` (checkpoint SQLite). It never asks TigerGraph. That is why the
screen showed prior counts on a fresh start and why it reported "loaded" for empty vertices.

**Fix — the screen's source of truth becomes the graph, with validation:**
1. Add a **graph-truth count** per entity, read live from the graph
   (`getVertexCount` / a count query), shown beside the checkpoint's claim.
2. Add **attribute validation**: for each entity, sample N rows (default 5) from the graph and
   verify that **non-primary-key attributes are actually populated**. Mark the entity
   `VALIDATED` only when (a) graph count matches expected **and** (b) sampled rows have
   non-empty non-PK attributes. Anything else is `MISMATCH` or `EMPTY_ATTRS`.
3. Display this as **validation proof** in the screen (see B6) — the counts, the sampled
   attribute check, and when it was validated.
4. Where checkpoint claim ≠ graph truth, the screen must show the conflict explicitly, not
   silently prefer one.

## A6 — Delete paths throw 500 (both single-entity and delete-all)

**Traced:** `ingestion_service.py:56` `delete_entity()` — the **vertex branch has no error
handling**:
```python
if config.kind == "vertex":
    result = graph.delete_all(config.tigergraph_vertex, kind="vertex")   # ← unguarded
else:
    try: ...  # edges are guarded
```
Any failure here raises → 500 → and because `delete_all_entities()` is a list comprehension
over `delete_entity()`, a single failure aborts the entire delete-all. (The CORS error seen
in the browser is a *symptom*: FastAPI's 500 response carries no CORS headers.)

**Fix:**
1. Guard the vertex branch the same way as edges: catch, record, and **continue**.
2. `delete_all_entities()` must **not** abort on one failure — collect per-entity results
   (`deleted` / `failed` + reason) and return a full report.
3. Verify the underlying `delete_all(kind="vertex")` is actually implemented on the
   TigerGraph tier; if pyTigerGraph `delVertices` is unavailable or unsupported for a type,
   report that plainly rather than raising.
4. Ensure error responses still carry CORS headers (add an exception handler that returns a
   proper JSON error) so the browser shows the real message instead of a CORS failure.

## A7 — Relative SQLite path resolves unpredictably

`sqlite_db_path` defaults to `./data/sqlite/iperform.db` — **relative to the process working
directory**, so the live DB moves depending on where the backend was launched. This cost
hours today (a checkpoint DB was deleted that the app was not using).

**Fix:** resolve all data paths against the **repo root** (or an explicit `APP_ROOT`), and
**log the absolute resolved path at startup** for the SQLite DB, the data set directory and
the manifest. The env-health screen must display these resolved absolute paths.

## A8 — Drop / recreate scripts (manual reset that always works)

Because delete-all cannot be fully trusted on a live graph, provide the V1-style escape hatch:
- `docs/tigergraph_foundation/tigergraph/schema/90_drop_all.gsql` — drops all `phx_dm_v2_*`
  edges, then vertices, then the graph, in correct order.
- Document in `RUNBOOK.md`: drop → re-run `01/02/03_*.gsql` → `install_all_queries.gsql` →
  clear checkpoints → Run All. This is the guaranteed clean-slate procedure.
- Also add a **clear-checkpoints** endpoint/CLI (`clear_entity` already exists in
  `checkpoint_repository.py:220` — expose it) so state can be reset without hunting for a DB
  file.

## A9 — Verification: what YOU verify vs what the OPERATOR verifies

**You cannot reach TigerGraph and the repo contains no real client data (`data/real/` is
gitignored).** Do not claim, simulate, or wait for live-TigerGraph verification. Split it:

### A9a — You MUST verify these yourself, before starting work-stream B
Use the local tier plus **real-shaped test fixtures** you create (see below). All of these
are fully verifiable in your environment:
1. **Attribute integrity:** load an entity and assert the stored rows contain **populated
   non-primary-key attributes** — not just the id. Prove A1 works.
2. **Fail-loud on mismatch:** deliberately rename a column in a fixture CSV; the load must
   **fail with a precise error naming the column**, not silently create empty rows.
3. **Quoting:** a fixture value containing a comma, a double-quote and a newline round-trips
   into the correct columns (A2).
4. **Line endings:** written CSVs are LF; a BOM-prefixed fixture still parses (A3).
5. **Checkpoint honesty:** simulate a failed upsert (inject an error in the adapter or point
   at a rejecting stub); the batch must be recorded **FAILED with no row hashes written**,
   and a subsequent reload must **retry** rather than skip as "Unchanged" (A4).
6. **Screen truth:** the status payload reports graph-derived counts **and** the attribute
   validation state, and flags checkpoint-vs-graph mismatch (A5).
7. **Deletes:** delete-one and delete-all complete without raising, and delete-all continues
   past a failing entity and reports per-entity outcomes (A6).
8. **Paths:** resolved absolute paths for the SQLite DB, data dir and manifest are logged at
   startup (A7).
9. **Idempotency:** running the full load twice produces identical counts, no duplicates, no
   false skips.

**Test fixtures:** create `data/fixtures/` (gitignored) — a small set of CSVs in the **exact
column shape of the real files** (same headers as `build_real_data.py` produces), including
at least one quoted-comma value, one BOM file, one file with a deliberately wrong column
name, and one with an empty optional value. These are your regression harness. They are NOT
sample demo data — they are test inputs.

### A9b — OPERATOR verification (write this checklist; do not attempt it)
Produce `docs/ROUND5_ACCEPTANCE.md` — a short, numbered checklist the operator runs against
**live TigerGraph with real data**, each step stating the exact command, expected result and
what to do on failure:
1. Drop + recreate schema (A8 scripts), install queries.
2. Clear checkpoints; confirm the resolved DB path in the startup log.
3. `build_real_data.py`; confirm reconciliation $0.00 and MIX per transition.
4. Run All; confirm **every** entity reaches `VALIDATED` (graph count matches **and** non-PK
   attributes populated).
5. Spot-check one vertex in GSQL showing populated attributes, not just an id.
6. Delete-one and delete-all; confirm no 500 and a per-entity report.
7. Re-run Run All; confirm idempotency.

Mark work-stream A `DONE (pending operator acceptance)` once A9a passes. **Do not block
work-stream B on A9b.**

---

# WORK-STREAM B — INGESTION SCREEN REBUILD

The screen is the operational source of truth. It must be honest, detailed and usable at
scale.

**B1 — Live per-entity progress.** During Run All show the **entity currently processing**,
its position (`12/45`), rows done/total for that entity, and a running tally of
created/updated/skipped/failed. Not just "1/45 entities".

**B2 — Async status refresh.** Status polls (e.g. every 2–5s) **without blocking or
restarting** the run, and without freezing the UI. Use the existing
`GET /ingestion/run-all/status`. The run continues if the browser is closed.

**B3 — Batch size visible.** Show the configured batch size per entity in the table, and make
it configurable (env + per-run override).

**B4 — Per-entity error details.** Each row expands to show: the error message, the failing
row number, the offending column/value where known, and **what to do next** (e.g. "column
`class_name` missing from CSV — regenerate with `build_real_data.py`"). Errors must be
persisted so they survive a page refresh.

**B5 — Skip-and-continue.** A failing entity is marked `FAILED`, **skipped**, and the run
**continues** to the next entity. At the end, present a remediation summary: which entities
failed, why, and the ordered steps to fix and re-run only those.

**B6 — Validation proof column.** Per A5: show graph count, expected count, attribute-check
result, and a `VALIDATED` / `MISMATCH` / `EMPTY_ATTRS` / `NOT_LOADED` state with the
timestamp of the check. This column is the answer to "did it really load?".

**B7 — Scale.** Implement what is reliable now: chunked/batched processing with resumable
checkpoints, async status, and no full-file materialisation in memory. Do **not** over-engineer
streaming this round — record "streaming ingestion for multi-million-row loads" in the
SOLUTION_GUIDE next-steps for a later round.

---

# WORK-STREAM C — DATA FILE NAMING & TRACEABILITY

> **Sequencing: do this LAST, after A, B and D are committed and green.** Renaming files
> touches the manifest, entity registry, builder, tests and docs at once — do not run this
> blast radius while ingestion is still being repaired. Commit it as its own change so it can
> be reverted independently.

**C1 — Name real CSVs after their vertex/edge type.** e.g.
`data/real/vertices/phx_dm_v2_revenue_class.csv`,
`data/real/edges/phx_dm_v2_txn_has_reason.csv`, so a file maps to its target at a glance.

**C2 — Update every reference consistently:** the manifest, `build_real_data.py` output
paths, the ingestion entity registry, the runbook, and any doc that names a file. **A single
catalog must define the mapping** (target ↔ file ↔ columns) and every consumer reads it —
no file name may be hardcoded in more than one place. Verify by grep after the change.

---

# WORK-STREAM D — FIRST-MONTH BASELINE (the MIX problem)

Real data showed MIX residuals of 92%–2197% on the **first transition only**
(`202604→202605`), while later transitions sit at 0–5%. Cause: April is the first month in
the dataset, so `NEW_ACCOUNT`/`LOST_ACCOUNT` have no true prior baseline — every account
looks new, and the residual lands in MIX. March data is **not available**, and in production
there will **always** be a first month with no prior period.

**D1 — Model the baseline month as a first-class concept.** Mark the earliest month in the
loaded data as `is_baseline = true`. For the transition **out of** the baseline month:
- Do **not** compute `NEW_ACCOUNT` / `LOST_ACCOUNT` (no valid prior period to compare).
- Attribute what those drivers would have claimed to a dedicated, honest driver:
  **`BASELINE_LIMITED`** (`data_source = DERIVED`), described as *"first period in the loaded
  data — account-level attribution requires a prior period."*
- MIX must not absorb it.

**D2 — Surface it in the UI and commentary.** The first transition shows a clear note:
*"April 2026 is the first month in the loaded data; account-level drivers are unavailable for
this transition."* Commentary must not narrate baseline-limited amounts as business events.

**D3 — Verify.** After D1, MIX on the first transition must fall below the 15% self-check
threshold for every advisor, and reconciliation must remain $0.00.

---

# WORK-STREAM E — REAL DATA IS THE ONLY DEMO PATH

The operator's standing rule: **demos and acceptance use real data only.** That rule governs
the operator, not your development loop — you have no real data and cannot produce it.

**E1 — Sample data is demoted to a test asset.** It must no longer be presented as a demo
path: remove it from the runbook's demo instructions and from any "try it with sample"
guidance. It may remain in the repo for automated tests, and `data/fixtures/` (A9a) is your
regression harness.

**E2 — The demo/acceptance path in all docs is `DATA_SET=real`.** Update `RUNBOOK.md` and
`SOLUTION_GUIDE.md` Chapter 9 so the documented path is real data end to end, with sample
mentioned only as a test fixture.

**E3 — Report honestly.** In `BUILD_REPORT.md`, state plainly which items you verified
yourself (A9a, local tier + fixtures) and which require operator acceptance against live
TigerGraph (A9b). **Never describe a fixture-based check as a real-data verification.**

---


---

## W10. IF BUDGET RUNS SHORT — PRIORITY ORDER

If the session cannot complete everything, land these in order; each is independently
valuable and committable:

1. **A1, A4** — attribute drop + checkpoint honesty. Without these nothing else is
   trustworthy. **Highest value; never skip.**
2. **A6, A8** — deletes + drop scripts. Without a working reset, the operator cannot recover.
3. **A5, B6** — graph truth + validation proof on the screen. Ends the "is it really loaded?"
   ambiguity.
4. **A2, A3, A7** — quoting, line endings, path resolution.
5. **B1–B5, B7** — screen progress, errors, skip-and-continue, scale.
6. **D** — baseline month / MIX.
7. **C** — file renaming (explicitly last).

Record in `PROGRESS.md` exactly where you stopped and what remains.

## W11. DEFINITIONS (do not guess these)

- **expected count** for an entity = the data row count of its source CSV (excluding header),
  which is what the manifest/registry reports. Not a hardcoded number.
- **VALIDATED** = graph count equals expected **AND** a sample of N rows (default 5, or all
  rows if fewer) each has at least one populated non-primary-key attribute.
- **EMPTY_ATTRS** = count matches but sampled rows carry only the primary key. This is the
  exact failure this round exists to eliminate — it must be visually distinct from VALIDATED.
- **MISMATCH** = graph count ≠ expected, or checkpoint claim ≠ graph truth.
- **baseline month** (D1) = the earliest `month_id` present in the loaded
  `phx_dm_v2_revenue_transaction` data — determined from data, never hardcoded.

## W14. REGRESSION SAFETY

- The existing verification scripts (`scripts/verify_end_to_end.py`,
  `scripts/validate_v2_queries.py`) must still pass at the end of the round. If a fix breaks
  them, fix the script only if the script was asserting the old broken behaviour — and say so
  in the report.
- Reconciliation must remain **$0.00 on every transition** after work-stream D.
- Do not change the credited-revenue definition, the reason model, the attribution formulas
  (other than D1), the schema, or any GSQL query. This round is ingestion reliability, not
  business logic.
- **The manual-upload path** referenced in A2 is the per-entity Upload action on the ingestion
  screen (frontend `components/ingestion/`, backend `POST /ingestion/run` with an uploaded
  file). Find and fix its parsing along with the batch path — the operator confirmed it
  behaves differently from Run All.


## W15. FILE CHANGE MANIFEST — `docs/ROUND5_CHANGED_FILES.md` (required)

The operator maintains a **separate client environment** with local modifications already in
place. They will copy only changed files across, not the whole project. Produce and keep
current a precise manifest so nothing is missed and nothing local is clobbered.

**Update it as you go** (not only at the end) — after each work-stream's commit, append that
work-stream's changes. If the session dies, the manifest must already reflect committed work.

### Required structure

```markdown
# Round 5 — Changed Files
Generated: <ISO timestamp>   Base commit: <hash before round 5>   Head: <hash>

## Copy these to the client environment

### Backend
| File | Change | Why |
|---|---|---|
| app/graph/tiered_client.py | MODIFIED | A1 attribute-drop fix |
| app/ingestion/ingestion_service.py | MODIFIED | A4 checkpoint honesty |
| ... | NEW / MODIFIED / DELETED | ... |

### Frontend
| File | Change | Why |
|---|---|---|

### Scripts / schema / docs
| File | Change | Why |
|---|---|---|

## DO NOT COPY — operator-local files
These commonly differ in the client environment; copying them would overwrite local settings.
| File | Reason |
|---|---|
| .env | operator has local TG credentials, SQLITE_DB_PATH, DATA_SET |
| data/real/** | client data, gitignored |
| data/fixtures/** | local test fixtures, gitignored |
| any *.db / *.sqlite | local runtime state |

## ⚠ REVIEW BEFORE COPYING — may conflict with operator edits
Files the operator is known to have edited locally. If this round also changed them, the
operator must MERGE rather than overwrite. State exactly what changed so a merge is possible.
| File | What round 5 changed | Operator may have changed |
|---|---|---|
| docs/data/source_catalog.json | <describe> | date window / table names |
| .env.example | <describe> | — |

## New directories to create
- data/fixtures/  (gitignored — do not copy contents)

## Post-copy steps
1. <e.g. re-run `uv run python scripts/generate_extraction_sql.py` if the catalog changed>
2. <e.g. restart backend so resolved paths are re-logged>
3. Follow `docs/ROUND5_ACCEPTANCE.md`
```

### Rules
- **Generate the file list from git, not from memory.** Use
  `git diff --name-status <base>..HEAD` and classify each path. A file you changed but did not
  list is a defect in this deliverable.
- **Flag every file the operator is known to have customised** (`.env`, `.env.example`,
  `docs/data/source_catalog.json`) in the REVIEW section with a description of your change,
  so they can merge instead of overwrite.
- List **deletions and renames explicitly** — the operator must remove/rename those files in
  the client env too, or stale copies will keep being used. This matters especially for
  work-stream C (file renaming).
- Keep it accurate over pretty; the operator copies from this list literally.

## W12. PROGRESS TASKS

| ID | Task |
|----|------|
| W-A1 | attribute-drop fix: pre-flight column validation, absent≠empty, zero-attr assert |
| W-A2 | CSV quoting correct on every read/write path incl. manual upload |
| W-A3 | write CSVs with LF; readers BOM-tolerant |
| W-A4 | checkpoint only after confirmed write; failures marked FAILED, no hashes |
| W-A5 | screen source of truth = graph count + attribute validation |
| W-A6 | delete-one / delete-all: guarded, non-aborting, CORS-safe errors |
| W-A7 | absolute path resolution + startup logging of resolved paths |
| W-A8 | 90_drop_all.gsql + clear-checkpoints endpoint + runbook procedure |
| W-A9 | work-stream A verification gate against live TigerGraph, real data |
| W-B1..B7 | screen: live per-entity progress, async refresh, batch size, error detail, skip-and-continue, validation proof, scale |
| W-C1 | real CSVs named after vertex/edge type |
| W-C2 | single catalog for target↔file↔columns; all consumers updated |
| W-D1 | baseline-month concept + BASELINE_LIMITED driver |
| W-D2 | baseline note in UI + commentary guard |
| W-D3 | MIX <15% on first transition; reconciliation $0.00 |
| W-E1 | sample data demoted to tests only |
| W-E2 | all verification with DATA_SET=real |
| W-F1 | ROUND5_CHANGED_FILES.md maintained per work-stream, git-derived, with conflict flags |

## W13. DEFINITION OF DONE

- [ ] All 45 entities load against **live TigerGraph with real data**; every entity
      `VALIDATED` (count matches **and** non-PK attributes populated)
- [ ] A corrupted/renamed column fails loudly instead of loading empty rows
- [ ] Quoted values containing commas land in the correct columns
- [ ] CSVs are LF; readers tolerate BOM
- [ ] Checkpoint never reports success for a write that did not land
- [ ] Screen shows graph truth + validation proof, and flags checkpoint/graph mismatches
- [ ] Delete-one and delete-all complete without 500 and report per-entity results
- [ ] Drop-all GSQL script + clear-checkpoints path documented in RUNBOOK.md
- [ ] Run All shows live per-entity progress, refreshes async, shows batch size and per-entity
      errors with remediation, and skips failed entities without aborting
- [ ] Real CSVs named after their vertex/edge type; one catalog drives every reference
- [ ] First transition MIX < 15%; `BASELINE_LIMITED` driver present; reconciliation $0.00
- [ ] No verification in this round used sample data
- [ ] `docs/ROUND5_CHANGED_FILES.md` complete and git-derived: every created/modified/
      deleted file listed, operator-local files excluded, conflict-risk files flagged
- [ ] `PROGRESS.md` all W-tasks DONE; `BUILD_REPORT.md` Round 5 section written
