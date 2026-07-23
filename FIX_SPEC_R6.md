# FIX SPEC — iPerform V2, Round 6 · ATTRIBUTION CORRECTNESS ON REAL DATA

> **Read completely before starting.** Supersedes earlier specs where they conflict.
> CLAUDE.md §0 (autonomous), §0.1 (PROGRESS), §3 (absolute rules) and rule 8a still apply.
>
> **Scope discipline:** this round fixes attribution correctness and two small carry-overs.
> It adds **no new features**. The conversational assistant, anomaly detection and book
> movement are round 7 — they must be built on numbers that are right.

---

## 0. THE PROBLEM (established from the first real-data build)

Round 5's ingestion fixes worked. The real-data build now runs, reconciles at **$0.00 on
every transition**, and the reason/eligibility model behaves. But the **attribution is
wrong**, and the MIX self-check is correctly screaming about it:

```
D194202 202604→202605   total change -154,811.92
  BASELINE_LIMITED  -267,500.38      ← over-claims
  MIX               +143,310.57      ← swings positive to compensate   (92.6%)

D194202 202605→202606   (NOT a baseline transition)
  LOST_ACCOUNT      -291,801.20
  NEW_ACCOUNT       +150,001.17      ← large, symmetric, every month
  MIX                +29,887.40      (18.8%)
```

Observed MIX on first transitions: 92.6%, 172.1%, 343.2%, 1061.0%, 2197.5%, 193.8%.

### Root cause — the account-presence test is wrong for real data

`app/v2/drivers/attribution.py` (~line 350) computes:
```python
advisor_new  = to_all - from_all      # traded this month, not last
advisor_lost = from_all - to_all      # traded last month, not this
```
A **two-month presence test** over **19,694 accounts / 73,324 transactions**.

On real data most accounts **do not trade every month**. An equities account that trades in
May and not June has not been lost — that is ordinary trading intermittency. So
`NEW_ACCOUNT` / `LOST_ACCOUNT` (and, out of the baseline month, `BASELINE_LIMITED`, which
inherits the same sets) massively over-claim, and MIX absorbs the error.

The sample data never exposed this because its accounts traded consistently in all months.

**This is not a baseline-month bug.** Round 5's `BASELINE_LIMITED` correctly stopped MIX
absorbing the *first* transition, but it inherited the same faulty account sets, so it
over-claims instead. Both must be fixed together.

**Why it matters:** commentary generated from this would tell an advisor they lost accounts
they did not lose. That is worse than a missing feature — it is a confidently-stated false
business claim, with evidence attached.

---

## A1 — Restrict account-presence drivers to products where monthly presence is meaningful

Absence of activity means something different by product type:

- **Recurring / fee-based** (product lines `Managed`, `Trails`): an account **should** bill
  every month. Absence is a real event worth naming.
- **Transactional** (Equities & Options, Structured Products, Alternative Investments,
  Fixed Income, Mutual Funds, Referrals, Cash Management, …): absence is **routine**. The
  change is already explained by `VOLUME`, `ONE_TIME` and `TIMING`.

**Fix:** compute `NEW_ACCOUNT` / `LOST_ACCOUNT` **only for groups in a recurring revenue
class**. The `is_recurring_class` flag is already passed into `attribute_group()` — use it
to gate the account-presence step.

For non-recurring groups, emit no account driver; `VOLUME` / `ONE_TIME` / `TIMING` carry the
change as they already do.

**Do not** simply move the amount to MIX — that reintroduces the residual problem. The
correct outcome is that the amount is claimed by the volume/one-time drivers that already
exist for those groups.

## A2 — Require persistence before declaring an account lost or new

Even within recurring lines, a single quiet month is not attrition.

- **LOST:** an account counts as lost only if it had activity in the from-month and **no
  activity for `ACCOUNT_ABSENCE_MONTHS` consecutive months** thereafter (config, **default
  2**), within the loaded data range.
- **NEW:** symmetric — an account counts as new only if it had **no activity in the
  preceding `ACCOUNT_ABSENCE_MONTHS` months** and then appears.
- Where the loaded data does not span enough months to apply the test (e.g. only one prior
  month exists), **do not emit the driver** — see A3.

Both settings live in config, not literals, and are reported in the build summary.

## A3 — `BASELINE_LIMITED` must reflect only what genuinely cannot be determined

`BASELINE_LIMITED` currently inherits the faulty sets and over-claims (−$267,500 against a
−$154,812 total change).

**Fix:** after A1 and A2, `BASELINE_LIMITED` may only carry amounts for **recurring-class
groups** where the account-presence test **cannot be evaluated** because insufficient prior
months are loaded. It must never exceed what the account-presence drivers would legitimately
have claimed. Everything else must be attributed to a real driver.

Sanity rule to implement as an assertion: `|BASELINE_LIMITED| ≤ |total_change|` for the
transition. A larger value means the sets are still wrong — fail the build with a clear
message rather than emitting it.

## A4 — Verification gate (this is the acceptance test for the round)

Using the **real data set** (the operator will run this; you verify on fixtures + sample):

1. **MIX < 15% on every transition, including first transitions.** This is the primary
   success measure. Current worst case is 2197%.
2. Reconciliation remains **$0.00 on every transition**.
3. `NEW_ACCOUNT` / `LOST_ACCOUNT` appear **only** for recurring-class groups.
4. `|BASELINE_LIMITED| ≤ |total change|` on every transition where it appears.
5. The build summary prints, per transition: total change, MIX %, and the count of accounts
   classified new/lost — so the operator can see the drivers are now plausible.

**Build a real-shaped fixture that reproduces the bug** — accounts that trade
intermittently in transactional products and consistently in Managed — and prove MIX drops
from >90% to <15% on it. Extend `scripts/verify_ingestion_fixes.py` (or add
`scripts/verify_attribution.py`) with these as automated checks.

## A5 — Reconsider the account-presence rule's downstream claims

`BUILD_REPORT.md` and `SOLUTION_GUIDE.md` currently describe `LOST_ACCOUNT` as accounts
leaving the advisor. After this fix, update that language to state the rule precisely:
*"accounts in recurring product lines with no billing activity for N consecutive months."*
Update the Revenue-Driver glossary entries for New Account and Lost Account to match.

---

## B — CARRY-OVERS FROM ROUND 5

**B1 — `90_drop_all.gsql` is broken and was never executable-tested.**
Two defects found on the live box:
1. It drops the graph **before** the queries. TigerGraph refuses — a graph cannot be dropped
   while its queries exist. Queries must be dropped first.
2. Reverse edges are **separate schema objects** (`reverse_phx_dm_v2_*`, declared via
   `WITH REVERSE_EDGE="..."`) and do **not** drop with their parent edge. They need explicit
   `DROP EDGE` statements.

Correct order: **queries → graph → reverse edges → forward edges → vertices.**
Generate the script from the schema files so it cannot drift (17 queries, 27 reverse edges,
27 forward edges, 18 vertices). Add a header note that "does not exist" errors are expected
and safe, while "still in use" is a real failure.

**B2 — Record the lesson in `BUILD_REPORT.md`:** GSQL authored here is *parse-reasoned*, not
executed. Any generated `.gsql` must be flagged `NEEDS-LIVE-VERIFICATION` until the operator
has run it, and the acceptance checklist must include running it.

---

# WORK-STREAM Y — ANOMALY DETECTION

> **Strict ordering: do not start Y until work-stream A is complete and MIX is under 15% on
> every transition.** Anomaly rules consume driver attribution. Built on today's attribution
> they would flag advisors for "losing $291k of accounts" that never left — a confidently
> stated false claim, with evidence attached. A must be right first.

Reference mockup: `docs/ui/reference/roadmap/02_anomaly_detection.png` (add it to the repo).

## Y1 — Detection is deterministic; only the wording is AI

Same boundary as everywhere else in this system. Rules are computed in Python over stored
drivers and revenue; the model may only phrase the finding. Every anomaly carries the figures
that triggered it and links to existing evidence.

## Y2 — Rules and thresholds (all config, with these defaults)

| Rule | Fires when | Default | Severity |
|---|---|---|---|
| `UNEXPLAINED_RESIDUAL` | `\|MIX\| / \|total change\|` exceeds threshold | **15%** | HIGH |
| `CLAWBACK_CONCENTRATION` | month's clawback total exceeds N× the advisor's trailing mean | **5×**, min $10k | HIGH |
| `LARGE_SWING` | `\|change_pct\|` exceeds threshold and `\|change_amt\|` exceeds a floor | **25%**, $50k | MEDIUM |
| `FEE_RATE_SHIFT` | effective rate moves more than N bps on a recurring group | **10 bps** | MEDIUM |
| `SINGLE_DRIVER_DOMINANCE` | one driver accounts for more than N% of the change | **70%** | LOW |
| `BASELINE_LIMITED_PRESENT` | transition contains a `BASELINE_LIMITED` driver | any | INFO |

Thresholds live in settings (`ANOMALY_*`), are surfaced in the UI, and appear in the build/
scan summary. Do not hardcode.

> **`BOOK_MOVEMENT` is deliberately excluded this round.** It depends on account movement
> being real, which work-stream A may show is largely trading intermittency. Re-evaluate in a
> later round once A's results are known.

## Y3 — Storage

New vertex `phx_dm_v2_anomaly`:
```
PRIMARY_ID anomaly_id STRING      # "<advisor>|<from_month>|<to_month>|<rule_id>"
advisor_sid STRING
from_month_id STRING
to_month_id STRING
rule_id STRING
severity STRING                   # HIGH | MEDIUM | LOW | INFO
title STRING
detail_text STRING                # AI-worded; carries the AI-generated chip in the UI
metrics_json STRING               # the figures that triggered it — computed, never model-authored
threshold_json STRING             # the config values in force when it fired
impact_amt DOUBLE
group_id STRING                   # "" when advisor-level
scan_id STRING
detected_at DATETIME
data_source STRING
```
Plus `phx_dm_v2_anomaly_scan` (scan_id, started_at, advisors_reviewed, transitions_reviewed,
flagged_count, thresholds_json, status) and edges
`phx_dm_v2_anomaly_for_advisor`, `phx_dm_v2_anomaly_in_scan`, `phx_dm_v2_anomaly_cites_driver`.

Scans are **additive and versioned** exactly like commentary — a new scan never deletes a
previous one.

## Y4 — Queries

Author with the usual discipline (file + catalog entry + local-tier impl + query case):
- `get_anomalies(STRING advisor_id, STRING scan_id, STRING severity, INT result_limit)` —
  `advisor_id=""` means all advisors; `scan_id=""` means latest scan.
- `get_anomaly_scans()` — scan history for the selector.

## Y5 — Detection service and trigger

`app/v2/anomalies/detection.py`, exposed as `POST /api/v2/anomalies/scan` with
`GET /api/v2/anomalies/scan/status`, mirroring the commentary generation workflow:
- **Batch, never on read.** The screen retrieves stored anomalies; it must not detect on page
  load.
- Re-scan creates a **new scan_id**; prior scans remain queryable.
- A CLI entrypoint (`python -m app.v2.anomalies.detection`) for headless client environments.

## Y6 — Narration

The `commentary_agent` gains an anomaly mode: given the rule, its metrics and thresholds, it
writes `title` and `detail_text`. The same guardrail applies — **every figure in the text must
exist in `metrics_json`**; violations block that anomaly's text and fall back to a
deterministic template rather than publishing unverified wording.

## Y7 — Screen (`/anomalies`, in the Results sub-nav)

Per the mockup:
- Header stating what was reviewed: *"Reviewed 10 advisors across 30 transitions and flagged
  4 items."* Transition selector, **Re-scan** button (themed), scan-version selector.
- Four stat cards: advisors reviewed · transitions · flagged · unexplained count.
- Severity-ordered cards with a coloured left rail, severity pill, rule tag, advisor, the
  AI-worded detail (with the **AI Generated chip**), the impact figure, and a specific action
  link (Open evidence / View transactions).
- Empty state when a scan found nothing: *"No anomalies above the current thresholds"* plus
  the thresholds in force — never a blank screen.
- A visible note that thresholds are configurable, with their current values.

## Y8 — Verification

- Fixtures that deliberately trigger **each** rule; assert each fires once and only once.
- Assert no anomaly's `detail_text` contains a figure absent from `metrics_json`.
- Assert re-scan is additive (prior scan still retrievable).
- Screen renders with zero console errors; empty state renders.


---

## C — WHAT NOT TO DO

- Do not build the conversational assistant — that is round 7 and needs a full session.
- Do not implement the `BOOK_MOVEMENT` anomaly rule (see Y2).
- Do not change the credited-revenue definition, the reason model, eligibility, the 90-day
  rule, the schema, or any GSQL query other than `90_drop_all.gsql`.
- Do not "fix" MIX by widening the threshold — the threshold is the detector, not the problem.
- Do not route unexplained amounts into `BASELINE_LIMITED` to keep MIX low. That is the bug
  this round exists to remove.

---

## D — PROGRESS TASKS

| ID | Task |
|----|------|
| X-A1 | account-presence drivers gated to recurring-class groups |
| X-A2 | persistence rule (`ACCOUNT_ABSENCE_MONTHS`, default 2) for new/lost |
| X-A3 | BASELINE_LIMITED bounded + assertion `\|BL\| ≤ \|total change\|` |
| X-A4 | fixture reproducing the bug; automated checks; MIX <15% everywhere |
| X-A5 | docs + glossary updated to the precise rule |
| X-B1 | 90_drop_all.gsql corrected (queries→graph→reverse→forward→vertices), generated from schema |
| X-B2 | BUILD_REPORT note: generated GSQL is NEEDS-LIVE-VERIFICATION |
| Y-1 | anomaly vertex/edges + scan vertex |
| Y-2 | six detection rules, thresholds in config |
| Y-3 | GQ queries + catalog + local-tier impls |
| Y-4 | detection service, batch scan endpoint + CLI, additive scans |
| Y-5 | anomaly narration via commentary_agent + guardrail |
| Y-6 | /anomalies screen per mockup, empty state, thresholds visible |
| Y-7 | per-rule fixtures; no-invented-figure assertion; additive re-scan verified |

## E — DEFINITION OF DONE

- [ ] MIX < 15% on **every** transition on the real data set (operator-confirmed), and on the
      bug-reproducing fixture (verified here)
- [ ] Reconciliation $0.00 on every transition
- [ ] `NEW_ACCOUNT`/`LOST_ACCOUNT` emitted only for recurring-class groups, and only after the
      persistence rule is satisfied
- [ ] `|BASELINE_LIMITED| ≤ |total change|` asserted; build fails loudly if violated
- [ ] Build summary reports MIX % and new/lost account counts per transition
- [ ] `90_drop_all.gsql` corrected and generated from the schema; header explains expected vs
      real errors
- [ ] Glossary and docs describe the account rule precisely
- [ ] `PROGRESS.md` all X-tasks DONE; `BUILD_REPORT.md` Round 6 section, separating verified-
      here from operator-pending
- [ ] Anomaly detection: all six rules fire on fixtures, thresholds configurable and shown,
      scans additive, narration passes the no-invented-figures guardrail, screen renders
      with zero console errors
- [ ] Work-stream Y was started only after MIX < 15% was achieved in work-stream A
- [ ] `docs/ROUND6_CHANGED_FILES.md` produced (same rules as round 5: git-derived, operator-
      local files excluded, conflict-risk files flagged)
