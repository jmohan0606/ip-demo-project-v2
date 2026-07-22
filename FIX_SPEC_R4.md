# FIX SPEC — iPerform V2, Round 4

> **Read this file completely before starting.** It supersedes `CLAUDE.md`, `FIX_SPEC.md`
> and `FIX_SPEC_R3.md` where they conflict; everything they define that this file does not
> change still applies — especially CLAUDE.md §0 (autonomous), §0.1 (PROGRESS protocol),
> §3 (absolute rules), rule 8a (AI-generated marking).
>
> Rounds 1–3 are complete and verified: credited-revenue is correct and data-driven,
> reconciliation is $0.00 with MIX <1.5% everywhere, the evidence and AI-Insights UX are
> built. This round does two things: **(A)** fix four demo-blocking UI defects found in
> client-environment testing, then **(B)** build and document the **real-data pipeline** so
> the app can run on actual client data on the client machine.
>
> **Do work-stream A first (it is demo-blocking and contained), then B.**

---

## 0. WORKING AGREEMENT (unchanged)

Autonomous, auto mode, no checkpoints, no questions. Append the S-prefixed tasks from §S10
to `PROGRESS.md`; do not renumber existing P/R/T tasks. Commit granularly, push after each
work-stream. Parallel subagents allowed in A only after each fix is independent; B is mostly
serial. Add a "Round 4" section to `BUILD_REPORT.md` at the end.

**Grounding rule:** every file path and line below was traced in the actual repo. If a line
number has shifted, find the real location — do not create a duplicate component or script.

---

# WORK-STREAM A — EVIDENCE & INSIGHTS UI CORRECTNESS (demo-blocking, do first)

Four defects, all found running the app in the client environment. None is a data-
correctness bug (reconciliation is still $0.00) — they are presentation-integrity bugs, but
#A2 in particular makes the evidence numbers appear not to tie, which destroys client trust.

## A1 — Glossary dialog causes 8 hydration errors (`<h2>` inside `<p>`)

**Cause (traced):** `GlossaryLink` (`frontend/components/patterns/revenue-driver-glossary.tsx:194`)
renders both a button **and** the dialog (`{open && <RevenueDriverGlossaryDialog/>}`) as
siblings. It is placed **inside a `<p>`** in two spots:
- `frontend/components/ai-insights/commentary-cards.tsx:120` — inside the description `<p>`
- `frontend/components/evidence/evidence-modal.tsx:672` — via `SectionHeader ... extra={<GlossaryLink/>}`

When opened, the dialog's `<h2>` (`revenue-driver-glossary.tsx:146`) lands inside that `<p>`,
which HTML forbids → hydration error, 8 times.

**Fix:** render `RevenueDriverGlossaryDialog` through a **React portal** to `document.body`
(`import { createPortal } from "react-dom"`), so it is never a DOM descendant of the
triggering element. This is the correct pattern for any modal/dialog. Apply the same portal
treatment to **any** dialog rendered inline this way — audit `evidence-modal.tsx` and the
glossary for other inline dialogs. Verify: open the glossary from both the AI-Insights
header and the evidence modal → zero console errors.

## A2 — Evidence modal mixes scopes; numbers don't tie (the $98 / $25 / −$165 bug)

**Cause (traced):** in one open modal, three panels describe **two different scopes**:
- **Header** and **Credited-revenue breakdown** are **group-scoped** (e.g. "Mutual Fund
  Trails", $2,020 → $1,855 = −$165)
- **Reconciliation waterfall** is **transition-scoped** (whole advisor, $43,820 → $65,182,
  all groups)

So the header says ▲$98 (one group's MIX driver), the waterfall shows the whole transition,
and the breakdown shows −$165 — three numbers that legitimately do not reconcile to each
other because they are not the same aggregation.

**Fix — one scope per modal, held across every panel.** The modal is opened about a specific
revenue driver, which belongs to a specific product group. Make the **entire modal
group-scoped** to that driver's group:
- Header: the group and that driver's contribution ✓ (already group-scoped)
- **Waterfall: rebuild for the clicked group only** — FROM = that group's from-revenue, TO =
  that group's to-revenue, bars = that group's drivers. It must sum to the group's change,
  not the transition's.
- Credited-revenue breakdown: the group ✓ (already group-scoped)
- Driver paging (A3): pages the drivers **within that group**.

Every number in the modal must now reconcile to the same group-level change. Verify on the
Mutual Fund Trails example: header change, waterfall FROM→TO, and breakdown delta all equal
the same figure.

> If a genuine transition-level ("all drivers") view is still wanted, it must be a **separate,
> explicitly-labelled** mode — never mixed silently into a group-scoped modal.

## A3 — Driver count inconsistent (cards show 5, modal pages 13)

**Cause:** AI-Insights cards show the top-5 ranked drivers; the evidence modal (after R3 T2
paging) pages **all** drivers across **all groups** in the transition ("Driver 3 of 13").
Both are internally consistent but the mismatch confuses users.

**Fix:** with A2 making the modal group-scoped, the modal now pages only the drivers **for
the clicked group** — a small, coherent set ("Revenue Driver 2 of 4" where 4 = that group's
drivers). Ensure the position indicator, Previous/Next, and ←/→ keys all operate over the
group's driver list, ordered by rank. The card's "top 5" and the modal's "all in this group"
are now both sensible and clearly different things (advisor-wide summary vs. one group's
detail). State this relationship in a one-line caption in the modal.

## A4 — Compare-two allows the same transition in both slots → duplicate React key

**Cause (traced):** `commentary-cards.tsx:265` keys each card `key={row.commentary_id}`;
`compareRows.map(card)` (≈ line 341) renders both selected transitions. Selecting the same
transition in both dropdowns yields two identical keys
(`v10|SMPL001|202605|202606`) → React "two children with the same key", and one card is
dropped.

**Fix — both of:**
1. **Prevent the meaningless selection:** in each compare dropdown, disable (or omit) the
   option already chosen in the other dropdown, so the same transition cannot be picked
   twice. Default the two dropdowns to two *different* transitions.
2. **Safety net:** make the key slot-scoped — `key={`${slotIndex}-${row.commentary_id}`}` —
   so an accidental duplicate can never crash the render.

Verify: in Compare-two, both dropdowns cannot select the same month; keys are unique.

## A5 — Regression sweep for work-stream A

After A1–A4: app boots in local mode, all screens render, **zero console errors** on:
AI-Insights (all three view modes), the glossary (both entry points), the evidence modal
(paging through a group's drivers), and Compare-two. Capture fresh Playwright screenshots
(R6 harness) proving each.

---

# WORK-STREAM B — REAL-DATA PIPELINE (the client-machine enabler)

Today the **sample** path works end to end, but the **real** path has a missing middle: the
3 extraction SQLs exist, and the ingestion screen loads `data/real/`, but **nothing builds
`data/real/` from the extracts.** `scripts/generate_sample_data.py` *fabricates* sample data
(it does not read the extracts). This work-stream builds and documents the real pipeline.

**Reuse, do not reinvent.** `generate_sample_data.py` already imports the real transform:
```
from app.v2.calendar import month_rows
from app.v2.drivers.attribution import attribute_transition, reconcile
from app.v2.revenue import eligibility as elig
from app.v2.revenue.aggregation import split_by_eligibility, (aggregation helpers)
```
The real-data builder must call these **same** functions. The only difference from the sample
generator is the **source of the transactions**: parsed from real extract CSVs instead of
fabricated. Everything downstream (eligibility, aggregation, attribution, reconciliation,
CSV writing, manifest) is identical and must be shared, not copied.

## B1 — Define the raw-extract contract (exact names and location)

The human runs the 3 SQLs in their Postgres client and saves CSVs. Specify **exactly**:

```
data/real/_raw/
  raw_revenue_transaction.csv   ← output of extract_revenue_transaction.sql
  raw_product_hierarchy.csv     ← output of extract_product_hierarchy.sql
  raw_advisor.csv               ← output of extract_advisor.sql
```

Document the **expected columns** of each raw file (they mirror the SELECT lists in
`docs/data/extraction/*.sql`). The builder validates presence and column names on load and
fails with a clear message naming the missing file/column — never a silent partial build.

## B2 — Build script `scripts/build_real_data.py`

CLI: `python -m scripts.build_real_data --raw data/real/_raw --out data/real`
(defaults to those paths). Behaviour:

1. **Read & validate** the three raw CSVs against the B1 contract.
2. **Parse transactions** from `raw_revenue_transaction.csv` into the same in-memory shape
   the sample generator produces (the `_mk_txn` row shape), mapping source columns →
   transaction attributes exactly as `EXTRACTION_SPEC` / the extraction SQL define
   (`post_split_credited_amt` → `credited_amt`, derive `rev_nature`, `reason_cd` →
   `revenue_eligibility` via `elig.reason_eligibility`, compute `days_to_process`, set
   `posting_month_id` = trade month **ASSUMED**, etc.).
3. **Build dimensions** from the raw hierarchy and advisor files: `product_line`,
   `product_group`, `product` (with `grid_type`), `advisor`, `account` (distinct from
   transactions), `reason_code` (from `elig.seed_rows()`), `revenue_class` (seeded),
   `month` (from `month_rows()` over the real date range), `driver_cause` (seeded, all 15
   including LATE_PROCESSING/EXCLUDED_CHANGE).
4. **Compute derived vertices** by calling the **same** functions the sample path uses:
   `split_by_eligibility` → `monthly_product_revenue`; MoM → `revenue_change`;
   `attribute_transition` → `revenue_driver`; then `reconcile` and **assert $0.00** on every
   transition (fail loudly if not — a real-data reconciliation failure is a stop condition).
5. **Write** `data/real/vertices/*.csv` and `data/real/edges/*.csv` with the **identical
   columns and order** as the sample set, and regenerate the manifest scoped to real.
6. **Stamp `data_source` on every row** (see B3).
7. Print a summary: rows per vertex, reconciliation result, MIX% per transition, and any
   OUT_OF_GRID / >90-day counts.

**Do NOT** generate commentary/evidence here — those remain the Regenerate-workflow's job,
created after load. `build_real_data.py` produces only extracted/derived vertices.

## B3 — `data_source` stamping (must match the sample rules exactly)

Every written row carries `data_source`, assigned by the same rules the sample generator
uses — real and sample data must be tagged identically:
- Straight from Postgres columns (advisor, product, account, transaction credited_amt,
  reason_code, grid_type) → **REAL**
- Computed by us (month calendar, monthly_product_revenue, revenue_change, revenue_driver
  for REAL causes, billable_days) → **DERIVED**
- `posting_month_id`, and any value resting on a stated assumption → **ASSUMED**
- `account_month_balance`, and MARKET / NET_FLOW drivers → **DUMMY**

Centralise these rules so the sample generator and the real builder call the **same** helper
(refactor if the sample generator currently inlines them). A row must never be written with a
blank `data_source`.

## B4 — Environment template `.env.example` (fully populated)

Provide a complete, commented `.env.example` covering every key the app reads, with real
placeholder shapes:
```
# --- graph tier ---
GRAPH_CLIENT_MODE=real            # real = TigerGraph, local = SQLite fallback
TIGERGRAPH_HOST=https://<host>
TIGERGRAPH_PORT=14240
TIGERGRAPH_GRAPH=iperform_v2_revenue
TG_USERNAME=<user>
TG_PASSWORD=<password>
TG_SECRET=<secret>                # if used by the adapter
# --- data ---
DATA_SET=real                     # real = data/real, sample = data/sample
# --- llm ---
LLM_CLIENT_MODE=claude            # claude | mock
ANTHROPIC_API_KEY=<key>
# --- credited-revenue config (R1) ---
CREDITED_GRID_TYPES=PRODUCT_TYPE
MAX_PROCESSING_DAYS=90
# --- ports ---
API_PORT=8001
```
Cross-check against `app/config/settings.py` so **every** setting the code reads is present
and named correctly. Any key the app reads but the template omits is a defect.

## B5 — Operations runbook (in `docs/SOLUTION_GUIDE.md`, Chapter 9)

Rewrite/expand the operations chapter into a **numbered, do-this-exactly** runbook for the
client machine. It must cover, in order:

1. **Prerequisites** — Python/node versions, TigerGraph reachable, env file created from
   `.env.example`.
2. **Install schema** — run `01_vertices.gsql`, `02_edges.gsql`, `03_create_graph.gsql`
   (exact commands / how to run against their TigerGraph).
3. **Install queries** — `install_all_queries.gsql`; note all 15 are
   `created-v2-NEEDS-LIVE-INSTALL` and this is the step that proves them.
4. **Extract data** — run the 3 SQLs in `docs/data/extraction/`, save as the B1 filenames in
   `data/real/_raw/`.
5. **Build real data** — `python -m scripts.build_real_data`; expect the reconciliation /
   MIX summary; a non-$0.00 result is a stop.
6. **Load** — ingestion screen (or CLI) with `DATA_SET=real`; verify loaded counts vs manifest.
7. **Generate commentary** — **the Regenerate button is the ONLY trigger; a fresh
   environment has no commentary until this is run.** Add a CLI equivalent
   (`python -m app.v2.commentary.generation_workflow`) for headless client environments and
   document it.
8. **Verify** — env-health shows `active_tier=1`, `served_by_tier=1` (green); spot-check a
   pivot total; open an evidence modal and confirm it ties out.
9. **Reload / reset** — the ordered delete path (reverse dependency order) for reloading data.

Each step: the exact command, the expected output, and the failure symptom + first thing to
check. Write it so someone who has never seen the project can run it.

## B6 — Verify the real path without a live TigerGraph

You cannot reach TigerGraph here, but you **can** prove the builder end to end in local mode:
- Create a **tiny synthetic raw-extract set** under `data/real/_raw/` (a handful of rows in
  the exact raw-column shape — clearly marked test fixtures, gitignored) and run
  `build_real_data.py` against it.
- Confirm it produces `data/real/vertices|edges/*` with the same columns as sample,
  reconciles to $0.00, stamps `data_source` correctly, and loads via the SQLite tier with
  `DATA_SET=real`.
- This proves the pipeline's logic; only the live-TigerGraph install/load remains a
  client-machine step. Record clearly in `BUILD_REPORT.md` what was proven locally vs. what
  still needs the client machine.

> `data/real/` stays gitignored. The test fixtures under `data/real/_raw/` must NOT be
> committed — verify with `git check-ignore`.

---

## S9. WHAT NOT TO DO THIS ROUND

- Do not implement iComp sourcing, prior-period adjustments, or Adjusted Credited Revenue —
  still documented open items.
- Do not change the credited-revenue definition, the reason model, or the attribution maths —
  they are correct and verified.
- Do not alter palette, chart colours, or layout.
- Do not generate commentary inside `build_real_data.py`.
- Do not commit anything under `data/real/`.

## S10. PROGRESS TASKS — append to `PROGRESS.md`

| ID | Task |
|----|------|
| S-A1 | Portal the glossary dialog; fix `<h2>`-in-`<p>` on both screens |
| S-A2 | Evidence modal single-scoped; waterfall rebuilt per clicked group |
| S-A3 | Driver paging scoped to the clicked group; consistent count + caption |
| S-A4 | Compare-two: prevent duplicate selection + slot-scoped keys |
| S-A5 | Regression sweep + fresh Playwright screenshots, zero console errors |
| S-B1 | Raw-extract contract (filenames, location, columns) documented + validated |
| S-B2 | `scripts/build_real_data.py` reusing app/v2 transform functions |
| S-B3 | `data_source` stamping centralised; sample + real use same helper |
| S-B4 | `.env.example` fully populated; cross-checked vs settings.py |
| S-B5 | SOLUTION_GUIDE Chapter 9 operations runbook (numbered, exact) |
| S-B6 | Prove real pipeline locally with test fixtures; document proven-vs-pending |

## S11. DEFINITION OF DONE (round 4)

- [ ] Glossary opens from both screens with zero hydration/console errors
- [ ] Every number in an open evidence modal reconciles to the same (group) scope; the
      $98/$25/−$165 class of mismatch is gone
- [ ] Evidence modal pages only the clicked group's drivers, with a clear count + caption
- [ ] Compare-two cannot select the same transition twice; no duplicate-key errors
- [ ] All screens render in local mode with zero console errors; fresh screenshots captured
- [ ] `scripts/build_real_data.py` turns raw extracts into `data/real/` vertex+edge CSVs by
      reusing the app's own transform functions
- [ ] Real and sample data are stamped with `data_source` by the same shared helper
- [ ] `build_real_data.py` asserts reconciliation $0.00 and reports MIX% + OUT_OF_GRID + >90d
- [ ] `.env.example` covers every key `settings.py` reads
- [ ] SOLUTION_GUIDE Chapter 9 is a complete, numbered client-machine runbook including the
      headless commentary-generation command
- [ ] Real pipeline proven locally with gitignored test fixtures; report states what remains
      a client-machine step
- [ ] `PROGRESS.md` all S-tasks DONE; `BUILD_REPORT.md` has a Round 4 section
