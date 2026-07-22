# ROUND 3 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2 in this repository. Rounds 1 and 2 are complete and
verified. This session applies round 3: one correctness fix, then an evidence and
AI-Insights UX overhaul based on client-environment testing. Work autonomously and
continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R3.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the T-prefixed tasks from FIX_SPEC_R3 §T10; do not renumber
   existing P/R tasks. If any T-task is already DONE, this is a RESUME — verify against
   `git log --oneline` and `git status`, continue from the first non-DONE T-task.
4. Skim `/BUILD_REPORT.md` and `/FIX_SPEC.md` for what rounds 1–2 built.

THEN work through T1 to T8 in order. T1 (the LATE_PROCESSING correctness fix) MUST be done
first and completely, on the main thread, before any UX work — it changes revenue
attribution and every downstream number. T2–T7 UX work may use parallel subagents only
after T1 is committed.

CRITICAL CONTEXT FOR T1: credited revenue = total − non_credited − excluded − late_excluded
− out_of_grid. The aggregation already tracks late_excluded, but attribution has NO driver
for it, so late-processing swings fall into the MIX residual and get narrated as "product
mix" — a wrong explanation with full evidence behind it. Add a LATE_PROCESSING driver,
symmetric with the existing ELIGIBILITY driver, and ensure every subtrahend in the identity
has a driver. After the fix, regenerate commentary as a new version and verify BOTH that
reconciliation is $0.00 AND that MIX is under 15% on every transition — a large MIX means a
driver is still missing.

KEY UX POINTS (full detail in the spec):
- Evidence modal must page through ALL drivers (Prev/Next), not show only "driver 1 of 5".
- Old commentary versions must not render empty evidence panels — backfill or label.
- Rename "cause" to "Revenue Driver(s)" in all UI text (labels only, not data fields).
- Add a Revenue-Driver glossary popup using the exact table in the spec.
- AI-Insights: remove the dead legend dropdown; add single/compare-two/all view modes;
  make chart arrows clickable; make the walk version selector static.
- Replace the DOM-scraping CSV export with a real data export (human headers, driver detail,
  built from stored data) plus a presentation PDF export.
- Fix the double-parenthesis header, theme the buttons, separate the AI chip from the
  computed count.

HOW TO WORK:
- Auto mode, continuous, no checkpoints, no questions.
- Update `PROGRESS.md` before and after every task and commit it (crash recovery).
- Commit granularly; push to origin main after each work-stream (T1, T2+T3, T4, T5, T6+T7,
  T8). If a push fails on auth, note it in PROGRESS.md and keep working.
- Component/file names in the spec came from the real repo — if a path differs, find the
  real one, do not create a duplicate.

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name ·
every fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback logged never silent · negatives in
parentheses · model-authored language carries an AI-generated chip and computed figures
never do.

IF BLOCKED: do not stop. Prefer honest provenance over invented data, record the decision in
PROGRESS.md under "Decisions", continue with the next task.

Begin with T1.

---
