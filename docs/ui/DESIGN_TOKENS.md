# DESIGN TOKENS — iPerform V2

These are the exact values used to render the mockups in `docs/ui/reference/`. Match them.
Put them in `frontend/components/design-system/design-tokens.ts` (which already exists) and
map them into `tailwind.config.ts` so components use token names, never raw hex.

---

## COLOUR

### Brand / chrome
| Token | Hex | Use |
|---|---|---|
| `navy` | `#10315B` | Top nav bar, section header bars, primary buttons, active nav |
| `navy-dark` | `#0B2444` | Active top-nav item background |
| `navy-ink` | `#12243B` | Code block background (evidence modal) |

### Surface
| Token | Hex | Use |
|---|---|---|
| `page` | `#F4F6F9` | Page background |
| `card` | `#FFFFFF` | Card / panel background |
| `header-bg` | `#E8EDF4` | Table header row |
| `group-bg` | `#EEF2F7` | Pivot group row (Recurring / Non-recurring) |
| `sub-bg` | `#F7F9FC` | Pivot sub-group row, card headers |
| `total-bg` | `#E3EAF3` | Total row |

### Text
| Token | Hex | Use |
|---|---|---|
| `text` | `#1C2530` | Primary |
| `muted` | `#63707F` | Secondary, labels, subtitles |
| `faint` | `#8B98A8` | Footnotes, axis labels, disabled |
| `link` | `#1B62B5` | Clickable figures, "View evidence ›" |

### Semantic
| Token | Hex | Use |
|---|---|---|
| `positive` | `#1E7A45` | Upward change, ✓, REAL badge text |
| `positive-bg` | `#E8F3EC` | Positive pill / badge background |
| `negative` | `#B3261E` | Downward change, ✗ |
| `negative-bg` | `#FBEAE8` | Negative pill background |
| `warn` | `#B7791F` | DERIVED / ASSUMED / DUMMY badge text, formula callout |
| `warn-bg` | `#FDF6E7` | Warn badge background |
| `purple` | `#5B3E90` | Vertex names, graph lineage |

### Chart
| Token | Hex | Use |
|---|---|---|
| `chart-recurring` | `#C2BE9E` | Recurring segment (khaki) |
| `chart-nonrecurring` | `#6193BD` | Non-recurring segment (steel blue) |
| `grid` | `#EEF1F5` | Chart gridlines |

### Border
| Token | Hex |
|---|---|
| `border` | `#D8DEE8` |
| `border-strong` | `#B9C4D2` |
| `border-subtle` | `#EDF1F6` |

---

## TYPE

Family: **Calibri / Carlito**, falling back to system sans
(`Calibri, Carlito, -apple-system, "Segoe UI", sans-serif`). This matches the client's
Office-native environment.

| Role | Size | Weight |
|---|---|---|
| Page title | 16px | 600 |
| Section header | 15px | 600 |
| Card title | 14px | 600 |
| Body / table cell | 11.5px | 400 |
| Table header | 10px | 600, `letter-spacing: 0.5px`, uppercase |
| Metric (large) | 19px | 600 |
| Delta value | 12.5px | 600 |
| Badge / tag | 9.5px | 600 |
| Footnote | 10.5px | 400, italic |

---

## SPACING & SHAPE

- Page padding `24px` · card padding `20px` · card gap `16px`
- Card radius `3px` · badge/pill radius `8–10px` (fully rounded ends) · button radius `3px`
- Table row height `24–27px` · header row `26px`
- Border width `1px`; card borders `1px solid border`

---

## NUMBER FORMATTING — enforce globally

Write one formatter and use it everywhere. This is a hard requirement, not a preference.

| Kind | Positive | Negative |
|---|---|---|
| Currency | `$512,340` | `($90,685)` |
| Currency (compact) | `+$23.8k` | `($44.1k)` |
| Percent | `9.3%` | `(17.7%)` |
| Change with direction | `▲ $43,430  9.3%` | `▼ ($90,685)  (17.7%)` |

**Never render a minus sign.** Negatives are parenthesised and coloured `negative`;
positives coloured `positive`. Zero renders as `—` in `faint`.

---

## PROVENANCE BADGES

Every non-real value must carry one. Small pill, 9.5px, uppercase.

| Value | Text | Background | Meaning |
|---|---|---|---|
| `REAL` | `positive` | `positive-bg` | Straight from client data |
| `DERIVED` | `link` | `#EEF2F7` | Computed by us from real data |
| `ASSUMED` | `warn` | `warn-bg` | Depends on a stated assumption |
| `DUMMY` | `warn` | `warn-bg` | Placeholder — no real data yet |

`DUMMY` and `ASSUMED` must additionally be explained on hover (tooltip stating what data
would make it real).

---

## CAUSE TAGS

Neutral pill, `header-bg` background, `navy` text, 9.5px, uppercase — deliberately quieter
than the provenance badge: `ONE-TIME` · `TIMING` · `VOLUME` · `FEE RATE` · `DISCOUNT` ·
`BILLABLE DAYS` · `MIX` · `NEW ACCOUNT` · `LOST ACCOUNT` · `CLAWBACK` · `MARKET` · `NET FLOW`

---

## STATES

Use the existing `patterns/async-state.tsx` for all four:
- **Loading** — skeleton rows matching final layout; never a bare spinner on a table
- **Empty** — say why and what to do ("No commentary generated yet — run generation")
- **Error** — plain message + retry; never a raw stack trace
- **Blocked** (commentary-specific) — amber, states the validation reason plainly

## SAMPLE-DATA BANNER
When `DATA_SET=sample`, a persistent `warn-bg` bar sits directly beneath the sub-nav:
**"Sample data — not client figures."** It is not dismissible.
