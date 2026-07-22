# ROUND 4 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2 in this repository. Rounds 1–3 are complete and
verified. This session does two things: (A) fix four demo-blocking UI defects found in
client-environment testing, then (B) build and document the real-data pipeline. Work
autonomously and continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R4.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the S-prefixed tasks from FIX_SPEC_R4 §S10; do not renumber
   existing P/R/T tasks. If any S-task is already DONE, this is a RESUME — verify against
   `git log --oneline` and `git status`, continue from the first non-DONE S-task.
4. Skim `/BUILD_REPORT.md` for what rounds 1–3 built.

THEN do work-stream A first (four contained UI fixes, demo-blocking), then work-stream B
(the real-data pipeline). Do not start B until A is committed and verified with zero console
errors.

WORK-STREAM A — the four defects, all traced to exact files/lines in the spec:
- A1: the "What do these mean?" glossary renders a dialog inside a <p>, causing 8 hydration
  errors on two screens — fix by rendering the dialog through a React portal to document.body.
- A2 (most important): the evidence modal mixes group-scope and transition-scope, so its
  numbers don't tie ($98 header vs $25 waterfall bar vs -$165 breakdown). Make the ENTIRE
  modal group-scoped to the clicked driver's product group — rebuild the waterfall for that
  group only, so header, waterfall FROM→TO, and credited breakdown all reconcile to the same
  group-level change.
- A3: driver paging must be scoped to the clicked group (not all 13 across the transition),
  with a consistent count and a one-line caption.
- A4: Compare-two lets the same transition be picked in both dropdowns → duplicate React key.
  Prevent the duplicate selection AND make the key slot-scoped.

WORK-STREAM B — the real-data pipeline. Today the sample path fabricates data; there is no
script that turns the 3 SQL extracts into data/real/ vertex CSVs. Build one, REUSING the
app's own transform functions (the sample generator already imports attribute_transition,
reconcile, split_by_eligibility, month_rows, eligibility — call the same functions; the only
difference is transactions come from parsed real extract CSVs, not fabricated ones). Deliver:
the raw-extract filename/column contract; scripts/build_real_data.py; centralised data_source
stamping shared by sample and real; a fully-populated .env.example cross-checked against
settings.py; the SOLUTION_GUIDE Chapter 9 operations runbook; and local proof of the pipeline
using tiny gitignored test fixtures (you cannot reach live TigerGraph — prove the logic in
local mode and record what remains a client-machine step).

CRITICAL RULES FOR B:
- build_real_data.py must assert reconciliation $0.00 on every transition and stop if not.
- Every written row must carry data_source (REAL/DERIVED/ASSUMED/DUMMY) via the shared helper.
- Do NOT generate commentary in the builder — that stays the Regenerate workflow's job.
- Do NOT commit anything under data/real/ (gitignored).

HOW TO WORK:
- Auto mode, continuous, no checkpoints, no questions.
- Update PROGRESS.md before and after every task and commit it (crash recovery).
- Commit granularly; push to origin main after each work-stream (A, then B sub-parts). If a
  push fails on auth, note it in PROGRESS.md and keep working.
- File paths/line numbers in the spec came from the real repo — if one shifted, find the real
  location; never create a duplicate component or script.

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name ·
every fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback logged never silent · negatives in
parentheses · model-authored language carries an AI-generated chip and computed figures never.

IF BLOCKED: do not stop. Prefer honest provenance over invented data, record the decision in
PROGRESS.md under "Decisions", continue with the next task.

Begin with A1.

---
