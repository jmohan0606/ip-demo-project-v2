# FIX SPEC — iPerform V2, Round 11 · PER-ADVISOR SCOPE, PROGRESS UX, TAXONOMY PATCH

> **Read completely before starting.** CLAUDE.md §0, §0.1, §3 and rule 8a still apply.
> Four work-streams. Do them in this order: A (taxonomy patch — quick, independent) →
> B (per-advisor scope + versions) → C (progress overlay + async) → D (sample-data
> completeness). B and C are coupled (the overlay needs async, which B restructures), so read
> both before starting B.
>
> Do not regress rounds 9 and 10. Reconciliation stays $0.00 throughout.

---

## A — TAXONOMY PATCH (do first, independent, quick)

Round 10's taxonomy is correct but incomplete against the REAL product hierarchy (now
confirmed from the client's `pcr.product_hierarchy` table). Two gaps:

**A1 — Add `Alternative Investments`.** The real hierarchy has
`level_one_product = "Alternative Investments"`, `level_two_product = "Alternative
Investments"` (product code `ALTI`), which round 10's taxonomy does not list — so a real ALTI
transaction hits `resolve_path` and is refused (which would STOP the build).
- Add `Alternative Investments` as a **NON_RECURRING** line.
- **Add a code comment:** classification assumed NON_RECURRING pending client confirmation;
  revisit if the client places it under recurring. (Same honesty pattern as other assumptions.)

**A2 — Only `PRODUCT_TYPE` grid rows reach the taxonomy.** The real hierarchy also contains
rows with `grid_type = NON_CREDITED_REVENUE` (Small Households, Personal Accounts, Transferred
Accounts) and `grid_type = PAY_TYPE_SUMMARY` (Grid, Referral 25% payout, Incentive
non-eligible, LOA). These are reason/pay-type rows, NOT recurring/non-recurring products.
- **Assert that `resolve_path` is only ever called for rows whose `grid_type` is
  `PRODUCT_TYPE`.** Filter non-`PRODUCT_TYPE` rows out BEFORE classification so they can never
  trip the ambiguity guard. If a non-PRODUCT_TYPE row reaches `resolve_path`, that is a bug —
  add a guard that logs it loudly rather than misclassifying.

**A3 — Verify.** A fixture built from the real hierarchy's distinct paths (all ~45 rows)
classifies every `PRODUCT_TYPE` row without a stop; the NON_CREDITED_REVENUE / PAY_TYPE_SUMMARY
rows are excluded before classification; `ALTI` resolves to non-recurring. Reconciliation
$0.00.

---

## B — PER-ADVISOR SCOPE AND PER-ADVISOR VERSIONS

**Today both Regenerate (commentary) and Rescan (anomalies) run ALL advisors and produce one
GLOBAL version** (`run_generation` / the anomaly scan iterate the full advisor list; a new
version supersedes the prior global one). The operator wants per-advisor scope.

**B1 — Commentary versions become per-advisor.**
- A commentary version is scoped to a single `advisor_sid`. Regenerating advisor A creates a
  new version for A only; advisor B's latest version is untouched. Advisor A may be on v3 while
  B is on v1.
- Add `advisor_sid` to `phx_dm_v2_commentary_version` (propagate through the full chain per R8
  A4b: DDL → schema_catalog + loading job → manifest → both builders → both tiers).
- "Supersede prior PUBLISHED" now applies **within an advisor**, not globally.
- The version selector on AI Insights shows versions **for the selected advisor**.

**B2 — Anomaly scans become per-advisor**, mirroring B1: `phx_dm_v2_anomaly_scan` gains
`advisor_sid` (or an ALL sentinel — see B3); a scan for advisor A does not replace advisor B's
scan; the scan-version selector on the Anomalies screen is per selected advisor.

**B3 — Two buttons each, on both screens:**
- **"Regenerate (this advisor)"** / **"Rescan (this advisor)"** — operates on the advisor
  selected in the dropdown. Creates/updates only that advisor's version/scan.
- **"Regenerate all"** / **"Rescan all"** — iterates every advisor (the current behaviour), used
  after a fresh data load. Each advisor still gets its own per-advisor version/scan (not a
  single global blob) so the per-advisor model is consistent.
- Label the buttons clearly so the operator always knows the scope before clicking (the current
  single button silently did "all" — that ambiguity is the bug).

**B4 — Reconciliation and integrity.** Per-advisor versioning must not change any computed
figure — it only scopes WHICH advisor's commentary/anomalies are (re)generated. Reconciliation
$0.00; existing figures for other advisors unchanged by a single-advisor regenerate.

**B5 — Verify.** Regenerate advisor A → A gets a new version, B unchanged. Regenerate-all →
every advisor gets its own new version. Same for rescan. The selectors show per-advisor
history. No global version/scan remains.

---

## C — PROGRESS OVERLAY (requires making the workflows async)

**Problem.** Regenerate and Rescan are synchronous batch calls — the request blocks until done,
so the client sees nothing "running" and the page doesn't refresh to the new version. The
operator wants a visible in-progress indication, then an automatic refresh to the latest
version.

**C1 — Make both workflows async with a status endpoint.** There is already a `_status` dict
and `get_status()` in the commentary workflow — build on it, do not invent a parallel one.
- The Regenerate / Rescan POST starts the job and returns immediately with a job/scan id.
- A status endpoint (`GET .../status`) returns state (`running` / `done` / `failed`), progress
  (current advisor / N of M, current phase), and on completion the new version/scan id.
- The job continues if the browser closes; status is queryable on return.

**C2 — Overlay UI on both screens.** On clicking a Regenerate/Rescan button:
- Show a non-blocking **overlay** indicating work is in progress, with the phase/progress from
  C1 (e.g. "Generating commentary — advisor 3 of 10"). For a single-advisor run it can be
  simpler ("Regenerating…").
- The overlay must make clear something is running behind the scenes — this is a demoable
  "the system is working" moment.
- **On completion, refresh to the latest version** automatically (select the new version in the
  selector and re-render) so the client sees the fresh result without a manual reload.
- On failure, show a clear error in the overlay (not a silent dismiss), with the reason.

**C3 — Poll, don't hang.** The overlay polls the status endpoint (e.g. every 1–2s). It must not
block the UI or re-trigger the job. Closing/reopening the screen mid-run rejoins the existing
job's status.

**C4 — Verify.** Clicking Regenerate/Rescan shows the overlay; status advances; on completion
the page shows the new version without a manual reload; a failure surfaces in the overlay;
closing and reopening mid-run rejoins the running job. Zero console errors.

---

## D — SAMPLE-DATA COMPLETENESS (standing principle + this round's backfill)

**Standing principle (add to CLAUDE.md / SOLUTION_GUIDE):** every use case the app supports
must be demonstrable on the **sample dataset**. When a feature is added, the sample data must
be extended to exercise it. A feature that only works on real data cannot be shown in a sample
demo and is a gap.

**D1 — Backfill the sample data so every current use case is demonstrable:**
- An account that flips **9G** between adjacent months → produces an `INHERITANCE` driver.
- An account that flips **9E** between adjacent months → produces a `HOUSEHOLD` driver.
- Both a **recurring Annuities** product (Trails → Annuities) AND a **non-recurring Annuities**
  product (Annuities → Fixed/Variable) present → proves dual-name classification live.
- A **chargeback on a Life/Insurance/Annuities** product → produces a `CLAWBACK` driver; and a
  reversal on another product that is NOT labelled CLAWBACK.
- A **mixed account** (recurring billing + a one-time annuity in the same month) → exercises the
  R9 one-time exclusion.
- Transactions that trigger **each anomaly rule** (unexplained residual, clawback
  concentration, large swing, fee-rate shift, single-driver dominance, baseline-limited
  present) so a sample Rescan surfaces real anomalies (not just LOW/INFO).
- The **91/92/9L** codes present so the eligibility flip is visible in sample credited totals.
- At least one clean **May→Jun / Jun→Jul** transition per advisor (MIX < 15%) so the demo has
  fully-attributed transitions to show.

**D2 — Keep sample reconciliation $0.00** and keep the sample generator deterministic. Document
in the sample generator which use case each crafted record exercises (a comment per scenario),
so future rounds can see what must be preserved.

**D3 — Verify.** On the sample dataset: an INHERITANCE, HOUSEHOLD, CLAWBACK, and one of each
anomaly rule all appear; the eligibility flip is visible; reconciliation $0.00; the whole demo
narrative is showable without real data.

---

## E — VERIFY R10 CARRY-OVER (do not rebuild)

Confirm the **Env Health LLM connectivity section** from round 10 is present and working
(writer / judge / assistant rows, reachable / model-found / unavailable, judge flags
"model not found"). If it regressed, fix it; otherwise just add a verification line. This is the
pre-flight check that de-risks the new async Regenerate — the operator should confirm the LLM
config before kicking off a long per-advisor run.

---

## F — WHAT NOT TO DO

- Do not regress rounds 9–10 (one-time exclusion, account lists, scoped chat, taxonomy,
  eligibility flip, INHERITANCE/HOUSEHOLD, chargeback scope).
- Do not change the VOLUME/DEAL_SIZE arithmetic, the eligibility partition, or the
  credited-revenue definition.
- Do not confirm Alternative Investments' class as final — it is an assumption pending the
  client.
- Do not implement the client's remaining driver-spec items (top-20 accounts view, per-reason
  ineligible trend, true-ups as a separate driver) — a later round.
- Do not touch ingestion / TigerGraph screens (Copilot).
- Do not build MDW roll-up, book movement, streaming ingestion, or the documentation round.

---

## G — VERIFICATION

You cannot reach TigerGraph or real data. Verify on fixtures + local tier; write operator-only
checks in `docs/ROUND11_ACCEPTANCE.md`; never call a fixture check a real-data check.

1. Taxonomy: all real-hierarchy PRODUCT_TYPE paths classify without a stop; ALTI →
   non-recurring; non-PRODUCT_TYPE rows excluded before classification.
2. Per-advisor: single-advisor regenerate/rescan touches only that advisor; regenerate/rescan-
   all gives each advisor its own version/scan; selectors are per-advisor; no global version.
3. Async + overlay: overlay shows on click, status advances, page refreshes to the new version
   on completion, failure surfaces, mid-run reopen rejoins.
4. Sample completeness: INHERITANCE, HOUSEHOLD, CLAWBACK, each anomaly rule, and the
   eligibility flip are all demonstrable on sample data; reconciliation $0.00.
5. Env Health LLM section present/working.
6. All existing suites pass; reconciliation $0.00; zero console errors; rounds 9–10 intact.

## H — PROGRESS TASKS

| ID | Task |
|----|------|
| P-A1 | taxonomy: add Alternative Investments (non-recurring, assumption noted) |
| P-A2 | only PRODUCT_TYPE rows reach resolve_path; guard + loud log otherwise |
| P-B1 | commentary versions per-advisor (advisor_sid on version, propagated, supersede within advisor) |
| P-B2 | anomaly scans per-advisor |
| P-B3 | two buttons each (this advisor / all) on both screens, clearly labelled |
| P-B4 | per-advisor selectors; other advisors unaffected by single regenerate |
| P-C1 | async workflows + status endpoint (build on existing _status) |
| P-C2 | progress overlay on both screens; auto-refresh to new version on completion |
| P-C3 | poll not hang; mid-run reopen rejoins |
| P-D1 | backfill sample data for every use case (9G/9E flip, dual Annuities, clawback, mixed acct, each anomaly, eligibility flip, clean transitions) |
| P-D2 | sample reconciliation $0.00; per-scenario comments in the generator |
| P-D3 | standing principle documented: new use cases ship with sample data |
| P-E1 | verify R10 Env Health LLM section |
| P-F1 | docs/ROUND11_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) |

## I — DEFINITION OF DONE

- [ ] Alternative Investments classifies as non-recurring (assumption noted); every real
      PRODUCT_TYPE path classifies without a stop; non-PRODUCT_TYPE rows never reach the taxonomy
- [ ] Commentary and anomaly scans are per-advisor with per-advisor versions; two clearly
      labelled buttons (this advisor / all) on both screens; other advisors unaffected by a
      single-advisor run
- [ ] Regenerate/Rescan run async with a status endpoint; a progress overlay shows on both
      screens and the page auto-refreshes to the new version on completion; failures surface;
      mid-run reopen rejoins
- [ ] Every current use case is demonstrable on sample data (INHERITANCE, HOUSEHOLD, CLAWBACK,
      each anomaly rule, eligibility flip, mixed account, clean transitions); reconciliation $0.00
- [ ] The standing "new use cases ship with sample data" principle is documented
- [ ] Env Health LLM connectivity section verified present/working
- [ ] Rounds 9–10 intact; all suites pass; reconciliation $0.00; zero console errors
- [ ] `PROGRESS.md` all P-tasks DONE; `BUILD_REPORT.md` Round 11 section separating
      verified-here from operator-pending; `ROUND11_CHANGED_FILES.md` produced
