# UI SPEC — iPerform V2

Reference images: `docs/ui/reference/*.png` — **open each one before building that screen.**
They are rendered at 1440px wide. Match layout, hierarchy and formatting.

> The **numbers in the mockups are illustrative**. They show layout and formatting, not
> expected values. Never hard-code them.

Read `DESIGN_TOKENS.md` first — colours, type, and the number-formatting rules are there and
are mandatory.

---

## 1. FRAMEWORK

- Next.js App Router, routes under `frontend/app/(dashboard)/`
- Frontend **port 3001**, backend **8001**
- Every screen: top nav (navy) → sub-nav → advisor context bar → content
- Every data view uses `patterns/async-state.tsx` for loading / empty / error

---

## 2. NAVIGATION

Replace `frontend/lib/navigation.ts` entirely. V2 has one top-level section:

**Results** → `Revenue` · `Transactions` · `Trends` · `AI Insights`

| Sub-nav | Route | Screen |
|---|---|---|
| Revenue | `/revenue` | Phase 2 — stub with a clear "not in this build" empty state |
| Transactions | `/transactions` | Drill-down target (§6) |
| Trends | `/trends` | Two pivot tables (§4) |
| AI Insights | `/ai-insights` | Chart + commentary (§5) |

Operations (not in the Results nav — reachable from a settings/admin entry):
`/data-ingestion` (§7) · `/env-health` (§8)

---

## 3. ADVISOR CONTEXT BAR

Below the sub-nav, on every Results screen (see any reference image):
- **Left:** `V236209 · Katherine Alvarez` (id · name; if name is blank, show id alone),
  then a pill `AGP 2.0 · 3 months`
- **Second row:** `Advisor` label, advisor dropdown (the ten), `Apply` button
- **Right:** `As of 30 Jun 2026`, and a live tier pill: green `● TigerGraph · tier 1`
  or amber `● Local store · tier 2`. In real mode showing tier 2, it is **red**.

Advisor selection persists across the four Results screens.

---

## 4. TRENDS — `/trends`
**References: `01_trends_revenue_by_month.png`, `02_trends_mom_change.png`**

Two stacked cards on one page (not separate routes).

### 4a. Credited Revenue — Months
Hierarchical pivot: rows = product hierarchy, columns = months.

- **Row structure**: `Total` → group rows (`Recurring`, `Non-recurring`) → sub-group rows
  (`Managed`, `Trails`, `Cash management`, …) → leaf rows (`Unified Managed Account`,
  `JPMCAP`, …). Indent 0 / 18 / 38px. Group and sub rows get a `▾` disclosure and tinted
  backgrounds (`group-bg` / `sub-bg`); leaves are white.
- **Columns**: one per month in range, right-aligned. Header uppercase (`APR 2026`).
- **Leaf values are `link`-coloured and clickable** → `/transactions` filtered to that
  month + product group (§6). Group/sub totals are not clickable.
- Expand/collapse per group; `Expand all` control top-right; `Export ⌄` beside it.
- Footnote: *"Figures are credited (post-split) revenue. Blue values open the Transactions
  view filtered to that month and product."*
- Data: **GQ-005**.

### 4b. Credited Revenue — MoM Change
Same row structure; columns are **transitions** (`Apr → May`, `May → Jun`).

- Each cell shows `$` and `%` together: `($10,000)   (8.0%)`, coloured by direction.
- Cells where `|%| ≥ 15` get a subtle pill background (`positive-bg` / `negative-bg`) to
  draw the eye to material moves.
- First month has no transition column — do not render an empty one.
- `from_revenue = 0` → show `n/a`, not `∞`.
- Data: **GQ-007**.

---

## 5. AI INSIGHTS — `/ai-insights`
**Reference: `03_ai_insights_walk.png`** — the most important screen.

### 5a. Chart card — "Credited Revenue — Month over Month"
- Stacked vertical bars, one per month: `chart-recurring` (bottom) + `chart-nonrecurring`
  (top). Total labelled above each bar.
- **Between consecutive bars: a connector arrow**, drawn from the top of one bar to the
  top of the next, `positive` green or `negative` red, with an arrowhead.
- Above each arrow, a pill: `▲ $43,430  9.3%` or `▼ ($90,685)  (17.7%)`.
- Legend top-right; period selector (`T-3 ⌄`) beside it.
- Y-axis `$0 / $140k / $280k / $420k / $560k`, gridlines `grid`.
- Recharts, following the conventions in `charts/revenue-trend-chart.tsx`.
- Data: **GQ-006** (bars) + **GQ-007** `__TOTAL__` rows (arrows).

**Scaling:** with 12 months the arrows compress. Below ~90px between bars, drop the pill
label and keep the arrow, with the value in a tooltip. Never let labels overlap.

### 5b. Commentary card — "What is driving the changes in my month-over-month credited revenue?"
That question **is** the section header. Subtitle: *"One card per month-over-month move ·
five drivers ranked by impact · every figure computed from graph data"*.

Header right: version selector (`v3 · 20 Jul 02:14 (latest)`), `⟳ Regenerate`, `Export ⌄`.

- **One card per transition, side by side**, filling the full width (no left panel).
- Card header (tinted by direction): `May 2026 → Jun 2026`, the delta
  `▼ ($90,685)  (17.7%)`, and `5,948 transactions` right-aligned.
- **Five driver rows** per card, ranked:
  - `✓` (positive) or `✗` (negative) in the semantic colour
  - **Bold title**: `Structured Products ($44.1k)`
  - Explanation line beneath
  - Right side: **provenance badge** (`REAL`/`DERIVED`/`DUMMY`) then **cause tag**
    (`ONE-TIME`)
  - `View evidence ›` link → opens the evidence modal for that `driver_id`
- Card footer: *"Contributions reconcile to the total change ✓"* — or, if reconciliation
  failed, an amber blocked notice with the reason.
- Data: **GQ-009** (commentary) joined to **GQ-008** (drivers).

**Empty state:** if no commentary exists for the selected version →
*"No commentary generated for this advisor yet."* + a `Generate commentary` button.
**Never generate on page load.**

### 5c. Commentary table
**Reference: `06_ai_commentary_table.png`** — a second card on the same route (or a toggle),
titled "Credited Revenue — Monthly Walk".

- Dark (`navy-ink`) header row. Columns: `MONTH` · `TOTAL REV` · `CHANGE $` · `CHANGE %` ·
  `COMMENTARY (REVENUE DRIVERS)` · `EVIDENCE`. `CHANGE` spans `$` and `%` with a rule above.
- One row per month; alternating row tint.
- The **baseline month** shows `—` for both change columns and, in italic `faint`:
  *"Baseline month — no prior period in the current data set."*
- Commentary column holds `narrative_text` — the flowing paragraph, not bullets.
- `Evidence ›` button per row → evidence modal for that transition's top driver.
- Footnote: *"Commentary is generated once per version and stored in the graph — it is
  retrieved, not recalculated, so figures are identical on every view."*

---

## 6. EVIDENCE MODAL
**Reference: `04_evidence_popup.png`** — this is what answers "how do we know this is right?"

Opens over any screen from any `View evidence ›` or `Evidence ›`. Width ~1120px, scrollable.

**Header:** `Evidence — Structured Products ($44,100)`, then
`May 2026 → Jun 2026 · Advisor V236209 · Katherine Alvarez · Driver 1 of 5`.
Right: provenance badge + cause tag + close.

**Five numbered sections** — use these exact headings (neutral, not condescending):

1. **Finding** — one or two sentences in a tinted panel.
2. **Calculation** — *"Each component is aggregated directly from transaction records in the
   graph."* A table: `Component · <from month> · <to month> · Change · Share of MoM`, a
   bolded total row, then the formula in a `warn-bg` callout.
3. **Source records** — *"The underlying transactions — open the full list to inspect every
   row."* Table: `TRADE REF · DATE · PRODUCT · ACCOUNT · TYPE · CREDITED · SPLIT`, ~5 rows,
   monospace ids. Footer: *"Showing 5 of 18 contributing transactions"* +
   `Open all 18 in Transactions ›`.
4. **Data lineage and integrity checks** — two panels side by side.
   *Left:* the graph path traversed — vertex names in `purple` with match counts, connected
   vertically. *Right:* automated checks, each `✓` + description + detail
   (reconciliation · figures traced to source · coverage complete · product mapping valid).
   A failed check shows `✗` in `negative` and must not be hidden.
5. **Reproduce this result** — *"Run the same query we ran. It returns the figures above,
   unchanged."* Dark code block with the GSQL call and real parameters, `⧉ Copy` button,
   then `Returned` and the actual JSON result in a `positive-bg` strip.
   **Below it, a second block: the PostgreSQL extraction SQL**, labelled
   *"Source extraction (PostgreSQL) — shown for lineage; not executed by this application."*
   with its own copy button, `source_table` and `source_row_count`.

**Footer:** `Commentary v3 · model … · prompt v1.2 · generated … · data snapshot … · query GQ-011`
and a `Close` button. **No "Open in Studio" button.**

Data: **GQ-012**.

---

## 7. TRANSACTIONS — `/transactions`

The drill-down target. Accepts `?advisor=&month=&group=`.

- Filter bar reflecting the active filters, each removable.
- Table: `TRADE REF · TRADE DATE · PRODUCT · GROUP · ACCOUNT · TYPE · CREDITED · SPLIT % · SOURCE FEED`
- Credited amounts right-aligned, negatives parenthesised in `negative` (clawbacks are
  meaningful here — do not hide them).
- Footer: row count and sum of credited revenue — **the sum must equal the pivot cell the
  user clicked from.** That equality is the point of this screen.
- Sortable columns; paginate above 200 rows.
- Data: **GQ-013**.

---

## 8. DATA INGESTION — `/data-ingestion`
**Reference: `05_data_ingestion.png`** — adapt the existing
`components/ingestion/data-ingestion-workspace.tsx`.

- Header: title, subtitle *"Load V2 vertices and edges into TigerGraph. Dependency order is
  enforced on both load and delete."*, then `Sample data ⌄` / `Delete all` / `▶ Run All Ingestion`.
- Four stat cards: `VERTEX TYPES` · `EDGE TYPES` · `ROWS LOADED` · `LAST RUN`.
- **Entity manifest table** in dependency order: `# · VERTEX / EDGE · KIND · SOURCE FILE ·
  EXPECTED · LOADED · STATUS · DATA · ACTIONS`.
  - `STATUS`: `● Loaded` (positive) / `● Awaiting` (warn) / `● Failed` (negative)
  - `DATA`: the provenance badge — `account_month_balance` shows `DUMMY` with `0` loaded,
    and that is correct, not an error
  - `ACTIONS`: `Upload` · `Reload` · `Delete` per row
- **Delete must cascade in dependency order** — edges before vertices, facts before
  dimensions — and always confirm. Show the order in the confirm dialog.
- Footnote explaining the ordering guarantee.
- Data: **GQ-014** + the ingestion API.

---

## 9. CONNECTIVITY & ENVIRONMENT HEALTH — `/env-health`

Adapt `components/env-health/env-health-workspace.tsx`. Keep V1's honesty contract.

- Overall pill: `CONNECTED` (green) / `DEGRADED` (amber) / `FAILED` (red).
- One card per dependency: **TigerGraph** · **LLM** · **Local store** · **Ingestion state**.
- TigerGraph card must show: `mode`, `graph`, `active_tier`, `active_tier_name`,
  `counts_served_by_tier`, `counts_source`, `schema_installed`, `vertex_type_count`,
  `total_vertices`, and per-type `row_counts`.
- **If `GRAPH_CLIENT_MODE=real` and the local tier is serving, the screen is RED** with an
  explicit message. Never green on a fallback.
- Reconciliation panel: ingestion loaded counts vs graph counts vs manifest expected — all
  three shown side by side, mismatches highlighted.
- `Re-check` button; response times per check.

---

## 10. CROSS-CUTTING

1. **Negatives in parentheses. Everywhere.** One shared formatter.
2. **Provenance visible.** Any `DERIVED` / `ASSUMED` / `DUMMY` figure carries its badge,
   with a tooltip saying what would make it real.
3. **Sample-data banner** when `DATA_SET=sample`.
4. **Nothing fabricated in the UI.** No placeholder text, no lorem ipsum, no invented
   advisor names. Empty state beats fake content.
5. **Keyboard**: modal closes on Esc; tables navigable; focus returns to the trigger.
6. **Responsive down to 1280px.** Below that, allow horizontal scroll on tables rather than
   collapsing the hierarchy.
7. **No client logos or brand marks.**
