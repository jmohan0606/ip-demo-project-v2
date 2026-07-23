# ROUND 5 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2. This round is an INGESTION RESCUE: the first real
load against live TigerGraph exposed that the ingestion path reports success while writing
nothing, silently drops every attribute, and its delete/reset paths throw 500s. Work
autonomously and continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R5.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the W-prefixed tasks from FIX_SPEC_R5 §W12; do not renumber
   existing tasks. If any W-task is already DONE, this is a RESUME — verify against
   `git log --oneline` and `git status` and continue from the first non-DONE W-task.

THEN work A → B → C → D → E in order. **Work-stream A must be complete and verified before
starting B.** Nothing else in this round matters until ingestion is trustworthy.

CRITICAL CONTEXT — every defect below is confirmed and traced:
- `app/graph/tiered_client.py:53` `_entry_attributes()` silently skips any column whose name
  does not match the CSV header, so vertices are created holding ONLY their primary key while
  the batch reports success. This is the main bug.
- `app/v2/dataset/builder.py:91` writes CSVs with CRLF because csv.DictWriter's default
  lineterminator is "\r\n".
- `app/ingestion/ingestion_service.py` writes checkpoint hashes and a "success" batch record
  based on PROCESSING rows, not on TigerGraph confirming the write. Observed: batch says
  created=2, 100% complete, while the graph holds 0 rows. Every later reload then hash-matches
  and skips as "Unchanged", making the failure permanent and invisible.
- The ingestion screen reads its loaded state from the checkpoint SQLite
  (`phx_dm_ingestion_batch`), never from the graph — so it reports "loaded" for empty vertices.
- `ingestion_service.py:56` `delete_entity()` has NO error handling on the vertex branch, so
  any failure 500s; `delete_all_entities()` is a list comprehension over it, so one failure
  aborts everything. The browser's CORS error is a symptom of the 500, not a CORS misconfig.
- `sqlite_db_path` is relative, so the live checkpoint DB moves depending on the launch
  directory.
- CSV values containing commas (quoted) are mis-split by at least the manual-upload path.

VERIFICATION — READ CAREFULLY, THIS IS WHERE PAST ROUNDS WENT WRONG:
You CANNOT reach TigerGraph, and the repo contains NO real client data (data/real/ is
gitignored). Do not wait for, simulate, or claim live-TigerGraph verification.
- **You verify (A9a):** build `data/fixtures/` — small CSVs in the exact column shape the real
  builder produces, including a quoted-comma value, a BOM file, a wrong-column file and an
  empty optional value. Use them plus the local tier to prove every fix: attributes actually
  populated, mismatch fails loudly, quoting round-trips, checkpoint marks FAILED and retries,
  deletes don't raise, idempotency holds.
- **The operator verifies (A9b):** write `docs/ROUND5_ACCEPTANCE.md` — a numbered checklist
  they run against live TigerGraph with real data. Do NOT block work-stream B on it.
- **Never describe a fixture-based check as a real-data verification.** In BUILD_REPORT.md,
  separate "verified here" from "requires operator acceptance".
- **Never trust the ingestion screen's own reporting as evidence** — it has been reporting
  success for writes that never landed. Assert against stored graph contents.

REAL DATA IS THE DEMO PATH (work-stream E): update RUNBOOK/SOLUTION_GUIDE so the documented
demo and acceptance path is DATA_SET=real. Sample data is demoted to a test asset only. This
governs the docs and the operator — not your development loop, which uses fixtures.

IF BUDGET RUNS SHORT: follow the priority order in FIX_SPEC_R5 §W10 — A1+A4 first (attribute
drop + checkpoint honesty), then A6+A8 (deletes + drop scripts), then A5+B6. Work-stream C
(file renaming) is explicitly LAST because of its blast radius.

FILE CHANGE MANIFEST (required): the operator runs a separate client environment with local
edits already in place and will copy only changed files across — not the whole project.
Maintain `docs/ROUND5_CHANGED_FILES.md` per FIX_SPEC_R5 §W15, updating it after EACH
work-stream's commit (not just at the end). Derive the list from `git diff --name-status`,
never from memory. It must separate: files to copy · operator-local files never to copy
(.env, data/real, *.db, fixtures) · files that may CONFLICT with the operator's own edits
(.env.example, docs/data/source_catalog.json) with a description of your change so they can
merge instead of overwrite · explicit deletions and renames · post-copy steps.

HOW TO WORK:
- Auto mode, continuous, no checkpoints, no questions.
- Update PROGRESS.md before and after every task and commit it.
- Commit granularly; push after each work-stream.
- Every file path and line number in the spec was traced in the real repo — if one has
  shifted, find the real location; never create a duplicate module.

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name ·
every fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback logged never silent · negatives in
parentheses · model-authored language carries an AI-generated chip, computed figures never.

IF BLOCKED: do not stop. Prefer an honest failure that is reported loudly over a silent
success. Record the decision in PROGRESS.md under "Decisions" and continue.

Begin with A1.

---
