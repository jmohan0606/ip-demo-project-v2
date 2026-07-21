# ROUND 2 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2 in this repository. The initial build is complete.
This session applies a round of corrections and enhancements. Work autonomously and
continuously.

FIRST, in this order:
1. Read `/FIX_SPEC.md` completely. It is the authoritative spec for this round and
   supersedes CLAUDE.md where they conflict.
2. Read `/CLAUDE.md` §0 (autonomous working), §0.1 (PROGRESS protocol) and §3 (absolute
   rules) — all still apply.
3. Read `/PROGRESS.md`. Append the R-prefixed tasks from FIX_SPEC §R10; do not renumber or
   remove existing P-tasks. If any R-task is already marked DONE, this is a RESUME — verify
   against `git log --oneline` and `git status` and continue from the first non-DONE R-task.
4. Read `/BUILD_REPORT.md` for what already exists.
5. Re-read `docs/tigergraph/SCHEMA_SPEC.md` and `docs/data/EXTRACTION_SPEC.md` before
   changing the schema or extraction.

THEN work through R1 to R9 in order. R1 is a correctness fix that changes every revenue
figure in the application — do it first and completely before anything else, because
everything downstream depends on the numbers being right.

CRITICAL CONTEXT FOR R1: the application currently computes Total Revenue and labels it
Credited Revenue. The client's authoritative definition excludes transactions carrying
ineligible reason codes. We never extracted `reason_cd`. Fixing this changes the pivots,
the chart, every MoM delta, every driver contribution and every commentary sentence.
Eligibility must be driven by data in a reason-code vertex, never hardcoded, so that
changing the seed data or relaxing the grid_type filter changes behaviour with no code
change. After the fix, regenerate commentary as a NEW version and re-verify that driver
contributions reconcile to $0.00 on every transition.

HOW TO WORK:
- Run continuously in auto mode. Do NOT pause for approval or stop at checkpoints.
- Update `PROGRESS.md` before and after every task and commit it — it is your crash
  recovery.
- Commit granularly with clear messages. Push to `origin main` after each work-stream
  (R1, R2+R3, R4, R5, R6+R7+R8, R9). If a push fails on auth, note it in PROGRESS.md and
  keep working — do not stop.
- Parallel subagents are appropriate for R4/R5/R6/R7/R8 once R1–R3 are committed. R1 must
  be done serially on the main thread — it touches schema, extraction, aggregation,
  attribution, commentary and evidence, and a missed call site leaves the app computing
  two different revenue numbers.
- Subagents may not commit, may not create GSQL queries, and may not edit the query catalog
  or mock modules.

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name ·
every fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback is logged never silent · negatives
in parentheses.

TRANSPARENCY (R7-2): every region of model-authored LANGUAGE must carry a visible
"AI Generated" chip — commentary cards, the walk table's commentary column, the evidence
modal's Finding section, and the judge's reasoning. Computed figures must NOT be marked:
no number, table, chart, calculation, source record, lineage check or query result gets the
chip. The boundary is the point — it shows the client exactly where the model is used and
where it is not.

IF BLOCKED: do not stop. Follow CLAUDE.md §11 — prefer honest provenance over invented
data, record the decision in PROGRESS.md under "Decisions", continue with the next task.

Begin with R1.

---
