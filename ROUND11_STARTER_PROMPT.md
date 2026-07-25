# ROUND 11 STARTER PROMPT — paste as the first message

Copy everything between the lines.

---

You are continuing work on iPerform V2. Four work-streams this round. Work autonomously and
continuously.

FIRST, in this order:
1. Read `/FIX_SPEC_R11.md` completely. It is authoritative for this round.
2. Read `/CLAUDE.md` §0, §0.1, §3 and rule 8a — all still apply.
3. Read `/PROGRESS.md`. Append the P-prefixed tasks from FIX_SPEC_R11 §H; do not renumber
   existing tasks. If any P-task is already DONE, this is a RESUME — verify against
   `git log --oneline` and continue from the first non-DONE P-task.

ORDER: A (taxonomy patch — quick, independent) → B (per-advisor scope + versions) → C (progress
overlay + async; coupled with B — read both before starting B) → D (sample-data completeness).
Do not regress rounds 9–10. Reconciliation stays $0.00 throughout.

A. TAXONOMY PATCH. The round-10 taxonomy is correct but incomplete vs the REAL product
   hierarchy (now confirmed from the client's pcr.product_hierarchy table). Two gaps:
   (A1) Add "Alternative Investments" (level_one and level_two = "Alternative Investments",
   code ALTI) as a NON_RECURRING line — it is missing and a real ALTI row currently hits
   resolve_path and is refused, stopping the build. Add a code comment: classification assumed
   NON_RECURRING pending client confirmation. (A2) The real hierarchy also has rows with
   grid_type = NON_CREDITED_REVENUE (Small Households, Personal Accounts, Transferred Accounts)
   and PAY_TYPE_SUMMARY (Grid, Referral 25% payout, Incentive non-eligible, LOA) — these are
   reason/pay-type rows, NOT products. Assert resolve_path is only ever called for grid_type =
   PRODUCT_TYPE rows; filter the others out BEFORE classification; if a non-PRODUCT_TYPE row
   reaches resolve_path, guard and log it loudly rather than misclassify.

B. PER-ADVISOR SCOPE + VERSIONS. Today both Regenerate (commentary) and Rescan (anomalies) run
   ALL advisors and produce ONE GLOBAL version. Change to per-advisor:
   - Commentary versions become per-advisor: add advisor_sid to phx_dm_v2_commentary_version
     (propagate DDL→schema_catalog+loading→manifest→both builders→both tiers), "supersede prior
     PUBLISHED" applies within an advisor, the AI-Insights version selector shows the selected
     advisor's versions. Advisor A can be on v3 while B is on v1.
   - Anomaly scans become per-advisor the same way (advisor_sid on phx_dm_v2_anomaly_scan).
   - TWO BUTTONS EACH on both screens, clearly labelled: "Regenerate (this advisor)" /
     "Rescan (this advisor)" operate on the dropdown-selected advisor; "Regenerate all" /
     "Rescan all" iterate every advisor (each still gets its OWN per-advisor version/scan, not a
     global blob). The current single button silently did "all" — that ambiguity is the bug.
   - Per-advisor scoping changes WHICH advisor is regenerated, never any computed figure.
     Reconciliation $0.00; other advisors unaffected by a single-advisor run.

C. PROGRESS OVERLAY (needs async). Regenerate/Rescan are synchronous today so the client sees
   nothing running and the page doesn't refresh. Make both async: there is already a _status
   dict and get_status() in the commentary workflow — build on it, do not invent a parallel one.
   The POST starts the job and returns a job/scan id; a GET .../status returns state
   (running/done/failed), progress (advisor N of M, phase), and on completion the new
   version/scan id; the job continues if the browser closes. UI: on click show a NON-BLOCKING
   overlay indicating work in progress with the phase/progress ("Generating commentary — advisor
   3 of 10"); on completion auto-refresh to the latest version (select it and re-render) so the
   client sees the fresh result without a manual reload; on failure show the reason in the
   overlay. Poll every 1-2s, do not block or re-trigger; closing/reopening mid-run rejoins the
   running job.

D. SAMPLE-DATA COMPLETENESS. STANDING PRINCIPLE (document in CLAUDE.md/SOLUTION_GUIDE): every
   use case must be demonstrable on SAMPLE data; new features must extend sample data to
   exercise them. Backfill now so the sample dataset demonstrates: a 9G flip (INHERITANCE), a 9E
   flip (HOUSEHOLD), both a recurring Annuities and a non-recurring Annuities product, a
   chargeback on Life/Insurance/Annuities (CLAWBACK) plus a non-labelled reversal elsewhere, a
   mixed one-time+recurring account (R9 exclusion), transactions triggering EACH anomaly rule,
   the 91/92/9L codes (eligibility flip visible), and at least one clean May→Jun/Jun→Jul
   transition per advisor (MIX < 15%). Keep sample reconciliation $0.00 and the generator
   deterministic; add a comment per crafted scenario.

E. Verify (do not rebuild) the round-10 Env Health LLM connectivity section (writer/judge/
   assistant rows, reachable/model-found/unavailable, judge flags "model not found"). This is
   the pre-flight that de-risks the new async Regenerate. Fix only if regressed.

NOT IN SCOPE / DO NOT: regress rounds 9–10; change VOLUME/DEAL_SIZE arithmetic, the eligibility
partition, or the credited-revenue definition; treat Alternative Investments' class as final
(it is a pending assumption); implement the client's remaining driver-spec items (top-20
accounts, per-reason ineligible trend, true-ups driver); touch ingestion/TigerGraph screens;
build MDW roll-up, book movement, streaming ingestion, or the documentation round.

VERIFICATION: you cannot reach TigerGraph or real data. Verify on fixtures + local tier per §G,
including a fixture from the real hierarchy's ~45 distinct paths (all PRODUCT_TYPE rows classify
with no stop, ALTI non-recurring, non-PRODUCT_TYPE excluded), per-advisor scope behaviour, the
async/overlay flow, and sample-data completeness. All existing suites must pass; reconciliation
$0.00; rounds 9–10 intact. Write docs/ROUND11_ACCEPTANCE.md (operator-only) and
docs/ROUND11_CHANGED_FILES.md (git-derived, conflict-risk flagged, operator-local excluded).

UNCHANGED ABSOLUTE RULES: the LLM narrates and never computes · never invent a query name ·
every fact carries REAL/DERIVED/ASSUMED/DUMMY · fallback logged never silent · negatives in
parentheses · model-authored language carries an AI-generated chip and computed figures never.

Begin with P-A1.

---
