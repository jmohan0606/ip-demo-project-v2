# FIX SPEC — iPerform V2, Round 3

> **Read this file completely before starting.** It supersedes `CLAUDE.md` and `FIX_SPEC.md`
> where they conflict; everything they define that this file does not change still applies —
> especially CLAUDE.md §0 (autonomous working), §0.1 (PROGRESS protocol), §3 (absolute rules)
> and rule 8a (AI-generated marking).
>
> Rounds 1–2 are complete and independently verified: credited-revenue is correct and
> data-driven, reconciliation holds at $0.00, the reason model works. This round fixes one
> real correctness gap, then overhauls the evidence and AI-Insights UX based on client-
> environment testing. **Correctness first (T1), then UX (T2–T6).**

---

## 0. WORKING AGREEMENT (unchanged)

Autonomous, auto mode, no checkpoints, no questions. Maintain `PROGRESS.md` — append the
T-prefixed tasks from §T10; do not renumber existing P/R tasks. Commit granularly, push
after each work-stream. Parallel subagents allowed only where noted, and only after T1 is
committed. At the end add a "Round 3" section to `BUILD_REPORT.md`.

**Grounding rule:** component and file names in this spec were taken from the actual repo.
If a path differs, find the real one — do not create a parallel duplicate.

---

## T1. CORRECTNESS — the missing LATE_PROCESSING revenue driver (do first)

### The problem
Credited revenue is defined by this identity, already implemented in aggregation
(`app/v2/revenue/aggregation.py`):
```
credited = total − non_credited − excluded − late_excluded − out_of_grid
```
`late_excluded_amt` (the 90-day rule) is tracked per bucket. But **attribution has no driver
for it.** `app/v2/drivers/attribution.py` has 12 causes — including `ELIGIBILITY` for the
non-credited delta — but nothing for the late-processing delta. So when late-excluded
revenue changes month over month, that change is **not attributed to a named driver and
falls into the MIX residual**, where the commentary agent narrates it as "product mix" — a
factually wrong explanation delivered with full evidence behind it. This is exactly the
failure mode the architecture exists to prevent. It does not show in the sample data only
because there is a single late transaction.

### The fix

**T1-1 — Add driver cause `LATE_PROCESSING`.** Symmetric with `ELIGIBILITY`:
```
LATE_PROCESSING.contribution = −(to_late_excluded_amt − from_late_excluded_amt)
```
i.e. if more revenue fell outside the 90-day window this month, credited revenue dropped by
that amount. `data_source = REAL` (it is computed from real dates). Seed it in the
`phx_dm_v2_driver_cause` vertex with a clear description, and slot it into the attribution
order immediately **after `ELIGIBILITY`** (both are "revenue that left the credited bucket"
adjustments and must be claimed before VOLUME/MIX).

**T1-2 — Every subtrahend in the identity must have a driver.** Audit the identity: `total`,
`non_credited` (→ ELIGIBILITY), `excluded`, `late_excluded` (→ LATE_PROCESSING now),
`out_of_grid`. If `excluded` or `out_of_grid` can change month over month for a group,
they need drivers too (name them `EXCLUDED_CHANGE` / `OUT_OF_GRID_CHANGE`, REAL). If by
construction they cannot vary (e.g. out_of_grid is always ~0 on real data), document that in
a code comment and in the report rather than leaving it unhandled.

**T1-3 — MIX must be a genuine residual of last resort.** After T1-1/T1-2, MIX should only
ever hold true product-mix effects. Add an assertion in attribution: if `|MIX|` exceeds a
configurable fraction (default **15%**) of a transition's absolute change, log a WARNING
with the breakdown — a large MIX means a driver is missing or mis-specified. This is a
self-check, not a block.

**T1-4 — Add a MIX-magnitude check to the verification suite / BUILD_REPORT.** Reconciliation
at $0.00 proves *completeness*, not *correctness* — MIX absorbs whatever named drivers don't
claim, so $0.00 holds no matter how wrong a named driver is. Report, per transition, MIX as
a % of total change, so a reviewer can see attribution quality at a glance.

**T1-5 — Regenerate commentary** (new version) and re-verify reconciliation at $0.00 on every
transition, AND that MIX is now small (<15%) on every sample transition. If it is not, a
driver is still missing — fix it before proceeding.

**T1-6 — Relabel `total_revenue`.** The field the UI calls "total" is actually
*total-within-credited-grid-types* — it already excludes `PAY_TYPE_SUMMARY` product rows.
On the sample this drops ~$59k across 3 rows; on real data it should be near-zero because
PAY_TYPE_SUMMARY rows key off reason/rr codes, not product codes (they drive a separate
client screen and are not additive product revenue). Rename the field/label to
`in_scope_revenue` (or footnote it clearly as "total within credited product grid types"),
and add to the verification a check that the OUT_OF_GRID bucket is near-empty — flag loudly
if it is not, as that would be a real surprise on live data.

---

## T2. EVIDENCE — multi-driver paging (fixes the "driver 1 of 5" bug)

**The bug:** the evidence modal (`frontend/components/evidence/evidence-modal.tsx`) opens for
a single `driverId` (shape `"advisor|from|to|group|CAUSE|seq"`). Launched from the monthly
walk — which is transition-level — it only ever shows the top driver ("Driver 1 of 5").

**T2-1 — Modal takes a driver SET, not one driver.** New props: the transition
(`advisor, from_month, to_month`), the ordered driver list (by rank), and an
`initialDriverIndex`. It renders one driver at a time with **Previous / Next** controls and
a position indicator ("Revenue Driver 2 of 5"). Keyboard: ←/→ page, Esc closes.

**T2-2 — Unify both entry points.**
- From the **monthly walk** `Evidence ›` button: open the modal at driver 1 with the full
  set for that transition.
- From a **month-over-month card** `View evidence ›` on a specific bullet: open at *that*
  driver's index, still with the full set so the user can page to the others.

**T2-3 — Load the full set efficiently.** Use `GQ-008 get_change_drivers` for the transition
and `GQ-012 get_evidence` per driver (lazy-load evidence as the user pages, or batch — your
call, but do not fetch all evidence up front if it makes the modal slow to open).

**T2-4 — Header must reflect the current driver** and update as you page (title, provenance
badge, revenue-driver tag, "Revenue Driver n of N").

---

## T3. EVIDENCE — old versions, waterfall, header cosmetics

**T3-1 — Old versions with no evidence must not render empty scaffolding.** Versions v1–v5
predate the judge (R5) and the richer evidence (R4), so they legitimately have no
independent-review / waterfall / attribution data. Two-part fix:
- **Backfill where possible:** for any historical version whose drivers still exist, run the
  evidence-assembly and judge over it so the sections populate. Prefer this.
- **Where genuinely unreconstructable, label explicitly:** *"Independent review and detailed
  evidence are available from version N onward."* and hide (not blank-render) the empty
  sections.
- **Rule:** every version selectable in the UI must render every evidence section, OR state
  plainly why it cannot. No empty panels that look broken.

**T3-2 — Reconciliation waterfall overhaul** (`evidence-modal.tsx`, WaterfallJson). Current
version is under-explained. Make it:
- **Lead sentence (plain English):** "This shows how {from_month}'s credited revenue of {X}
  became {to_month}'s {Y}. Each bar is one revenue driver's contribution; because every
  dollar of change is attributed, the bars sum exactly to the total change."
- **Start and end bars** (from-revenue, to-revenue) in neutral; **driver bars** coloured
  green (up) / red (down) by direction.
- **Highlight the driver currently in focus** — as the user pages drivers (T2), that
  driver's bar highlights. This ties the waterfall to the paged detail.
- **"How to read this" expander** with a two-line explanation.
- **Completeness note:** a subtle caption — "The bars reconcile to $0.00, confirming every
  dollar of change is accounted for. A large unexplained (MIX) bar would indicate a missing
  driver." This turns the visual into an honesty self-check and pre-empts the reviewer's
  question.

**T3-3 — Fix the double-parenthesis header.** A negative transition change renders as
`(($7,000))` — the header wraps an already-parenthesised value again. Fix: in the header,
show `▼ ($7,000)` (arrow = direction, single parentheses = sign) in the negative colour;
positive shows `▲ $7,000` in the positive colour. Guard the formatter so it never
double-wraps. Audit every other header/badge for the same double-format bug.

---

## T4. TERMINOLOGY & THE REVENUE-DRIVER GLOSSARY

**T4-1 — Rename "cause" → "Revenue Driver(s)" everywhere in the UI.** This is the client's
own term and reads as meaningful. Change **labels, headings, tooltips and column names only**
— keep `cause_id` and the internal identifiers unchanged (do not rename data fields, queries
or vertex attributes; this is a presentation change).

**T4-2 — Drivers get their own column with a header in the month-over-month cards.**
Today the ✓/✗ rows sit under the transition with only tags to identify them. Restructure each
card so the drivers are under an explicit **"Revenue Drivers"** column header, so a first-time
viewer understands what those rows are. Keep the provenance badge and the (renamed) driver
tag on each row.

**T4-3 — Revenue-Driver glossary popup.** A single dialog, openable from a "What do these
mean?" link on both the AI-Insights and evidence screens, listing **every** revenue driver
with: the display name, a plain-English meaning, and **how it is computed/derived**. Use the
exact text below (this is also the source for the SOLUTION_GUIDE calculation chapter — write
once, reference from both):

| Revenue Driver | What it means | How it is computed |
|---|---|---|
| **New Account** | Revenue from accounts active this month that were not active last month | Accounts with credited transactions in the current month but none in the prior month, evaluated at advisor level so a mere product switch is not miscounted as a new account. Contribution = Σ credited revenue of those accounts. |
| **Lost Account** | Revenue lost from accounts active last month but not this month | Mirror of New Account: accounts credited last month, none this month. Contribution = −(their prior-month credited revenue). |
| **One-Time** | Non-recurring items such as syndicate allocations, new issues, referrals | Change in revenue tagged one-time (from `file_key` and `trade_description`) between the two months. |
| **Eligibility** | Revenue moving into or out of *credited* status | Change in non-credited revenue for the group (e.g. a household crossing the minimum-household threshold moves revenue from credited to non-credited). Contribution = −(Δ non-credited). |
| **Late Processing** | Revenue excluded because it processed more than 90 days after the trade | Change in revenue failing the 90-day rule (`proc_dt − trade_dt > 90`). Contribution = −(Δ late-excluded). |
| **Timing** | Quarterly or periodic billing landing in one month but not the other | Revenue for a group present in one month's billing cycle and absent the other, not already claimed by One-Time. |
| **Fee Rate** | Change in the effective fee rate charged | Prior-month asset proxy × (this month's avg rate − last month's), in bps. |
| **Discount** | Change in fee discounting / concessions | Change in Σ discount amount and in the count of discounted transactions. |
| **Billable Days** | A different number of billing days between the two months | Recurring/fee-based revenue × (Δ billable days ÷ prior billable days). Derived from a business-day calendar. |
| **Volume** | More or fewer transactions at similar rates | (Δ transaction count) × prior-month average transaction value, for transaction-based groups. |
| **Product Mix** | The residual shift between products at different rates | Whatever remains after all named drivers are attributed. A large value here means a driver may be missing. |
| **Clawback** | Reversals / chargebacks (negative revenue) | Change in the sum of negative credited amounts between the months. |
| **Market** | Movement in asset values *(not yet sourced — shown as illustrative)* | Requires an index-return feed not currently available. Modelled, flagged, contributes $0 until data is supplied. |
| **Net Flow** | Client inflows and outflows *(not yet sourced — shown as illustrative)* | Requires a flows feed (current source stops Jan 2026). Modelled, flagged, contributes $0 until data is supplied. |

Mark the Market/Net Flow rows in the glossary with the DUMMY/illustrative badge so the
client sees exactly which drivers are live and which await data.

---

## T5. AI INSIGHTS — view modes, clickable chart, dead controls, version selector

`frontend/components/ai-insights/insights-chart-card.tsx`, `commentary-cards.tsx`,
`monthly-walk-table.tsx`.

**T5-1 — Remove the dead legend dropdown** next to the Recurring/Non-recurring legend on the
chart. It has no function. Remove it (do not leave a disabled control).

**T5-2 — View-mode control** for the driver section below the chart, designed for the
12-month target state. One segmented control with three modes:
- **Single transition** (default for demo) — one month-over-month, full driver detail. A
  dropdown selects *which* transition (e.g. "May 2026 → Jun 2026"). With 12 months this is
  the primary way to focus.
- **Compare two** — the current side-by-side two-card view, with two dropdowns to pick which
  transitions.
- **All transitions** — links to / shows the monthly walk table.

**T5-3 — Chart arrows are clickable.** Clicking a connector arrow on the chart selects that
transition and switches the section to **Single transition** mode for it. The selected
arrow highlights. This is the primary drill interaction.

**T5-4 — Monthly-walk version selector becomes static text.** There are two version
selectors today (top section + walk); the walk one is a non-functional dropdown. Make the
walk inherit the top selector and display the active version as static text ("Version 6").

---

## T6. EXPORTS — real data export + presentation PDF

The current CSV (`frontend/components/ai-insights/export-csv.ts`) scrapes rendered UI values,
uses raw `snake_case` headers, copies stray values, and omits drivers. Replace with two
distinct, clearly-labelled exports.

**T6-1 — Data export (CSV/Excel).** Built from the **stored data via the API**, never scraped
from the DOM. One row per (transition, revenue driver), columns with human headers:
`Advisor`, `From Month`, `To Month`, `Total Revenue`, `Credited Revenue`, `Change ($)`,
`Change (%)`, `Revenue Driver`, `Driver Contribution ($)`, `Direction`, `Data Source`,
`Commentary`. Negatives parenthesised. It must match what the month-over-month section shows
— same drivers, same numbers. Provide the same for the monthly walk (one row per month with
its commentary and its drivers).

**T6-2 — Presentation export (PDF).** A print-styled, full-page PDF of the AI-Insights view
(chart + the selected driver detail) that the client can drop into a deck as-is. Implement
as a **print stylesheet + `window.print()` / headless render**, not a bitmap screenshot, so
it stays crisp and vector-clean. Include the advisor, the as-of date, the version, and the
AI-generated boundary note in the print footer.

**T6-3 — Two clearly-labelled buttons** ("Export data" / "Export PDF"), themed per T7. The
AI-generated marking (rule 8a) must appear in both exports' output.

---

## T7. COSMETIC — button theming (no theme/colour change)

**T7-1 — Generate/Regenerate/Export buttons currently have no colour.** Apply the existing
theme: primary navy fill for Generate/Regenerate (the main action), secondary outline style
for Export buttons. Use the design tokens; do not introduce new colours. Ensure hover/focus
states and disabled states are styled.

**T7-2 — AI-generated chip adjacency** on the commentary card header — the computed
transaction count currently sits directly beside the AI-generated chip, implying the count is
AI-generated. Separate them: the chip applies to the narrative wording only; move the
computed count to a visually distinct position (or add a hairline separator) so it is clear
the number is computed, not generated.

---

## T8. TWO QUICK CHECKS (do and report, ~1 minute each)

**T8-1 — `.gitignore` line endings.** Run `file .gitignore`. If it reports CRLF, the ignore
rules may be inert. Confirm `data/real/` is genuinely ignored (`git check-ignore data/real/x`
should print the path). Fix to LF if needed. This protects real client data from being
committed.

**T8-2 — `app/models` tracked.** Confirm `git ls-files app/models | head` returns files (the
round-2 `.gitignore` fix). If empty, the package is still untracked and a fresh clone will
not boot — fix the ignore rule.

---

## T9. WHAT NOT TO DO THIS ROUND

- Do not implement prior-period adjustments, iComp sourcing, or Adjusted Credited Revenue —
  these remain documented open items for the client (see FIX_SPEC R9.10 / SOLUTION_GUIDE).
- Do not split the ELIGIBILITY driver into status-change vs volume — that is a client
  question, not a build decision. Leave as-is; note it in the report.
- Do not change the palette, chart colours, or overall layout structure.
- Do not touch the credited-revenue definition or the reason model — they are correct.

---

## T10. PROGRESS TASKS — append to `PROGRESS.md`

| ID | Task |
|----|------|
| T1-1 | LATE_PROCESSING driver cause + seed |
| T1-2 | audit identity subtrahends for missing drivers |
| T1-3 | MIX >15% self-check (WARNING) |
| T1-4 | MIX-magnitude in verification/report |
| T1-5 | regenerate commentary; reconcile $0.00 + MIX small |
| T1-6 | relabel total_revenue → in_scope; OUT_OF_GRID near-empty check |
| T2-1 | evidence modal takes driver SET + Prev/Next |
| T2-2 | unify walk + card entry points |
| T2-3 | efficient full-set load |
| T2-4 | header reflects current driver |
| T3-1 | old-version evidence: backfill or explicit label |
| T3-2 | reconciliation waterfall overhaul + focus highlight |
| T3-3 | fix double-parenthesis header |
| T4-1 | rename cause → Revenue Driver(s) in UI |
| T4-2 | drivers as a titled column in cards |
| T4-3 | Revenue-Driver glossary popup |
| T5-1 | remove dead legend dropdown |
| T5-2 | view-mode control (single / compare two / all) |
| T5-3 | clickable chart arrows → single view |
| T5-4 | static walk version selector |
| T6-1 | real data export (CSV/Excel) from stored data |
| T6-2 | presentation PDF export |
| T6-3 | two themed export buttons + AI marking in output |
| T7-1 | button theming |
| T7-2 | AI-chip adjacency on card header |
| T8-1 | .gitignore CRLF / data/real protection |
| T8-2 | app/models tracked |

## T11. DEFINITION OF DONE (round 3)

- [ ] LATE_PROCESSING driver exists and fires; every identity subtrahend has a driver or a
      documented reason it cannot vary
- [ ] MIX < 15% on every sample transition; >15% logs a WARNING; MIX% reported per transition
- [ ] Reconciliation still $0.00 on every transition after regeneration
- [ ] `total_revenue` relabelled; OUT_OF_GRID near-empty check in place
- [ ] Evidence modal pages through all drivers (Prev/Next) from both walk and card entry
      points; header tracks the current driver
- [ ] Every selectable version renders every evidence section or states why it cannot; no
      empty scaffolding
- [ ] Waterfall has plain-English lead, focus highlight, how-to-read, completeness note
- [ ] No double-parenthesis anywhere; negatives coloured and single-parenthesised
- [ ] "Revenue Driver(s)" replaces "cause" in all UI text; drivers have a titled column;
      glossary popup lists all 14 with meaning + computation
- [ ] AI-Insights: dead dropdown gone; three view modes; clickable arrows; static walk
      version
- [ ] Data export from stored data with human headers and driver detail; presentation PDF
      export; both themed and AI-marked
- [ ] Buttons themed; AI chip not adjacent to computed count
- [ ] T8 checks done and reported
- [ ] App boots in local mode, all screens render, zero console errors
- [ ] `PROGRESS.md` all T-tasks DONE; `BUILD_REPORT.md` has a Round 3 section
