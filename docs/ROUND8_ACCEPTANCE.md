# Round 8 — Operator acceptance checklist

Everything below **cannot be verified on the build box** (no TigerGraph, no real data)
and needs the operator on the client machine. Everything that *could* be verified here
was: all suites pass (attribution 15 checks, queries, anomalies --rescan, e2e,
assistant 84/84), reconciliation $0.00 on every transition, 15/15 UI screenshots with
zero console errors, and the data-only rename proof (editing a seed `display_name`
changed the API/UI name with no code edit). Those were **fixture/sample-tier checks,
not real-data verification.**

## 1. Live schema + query reinstall (required — the vertex changed)

`phx_dm_v2_driver_cause` gained `display_name`, `description`, `computation`.
On live TigerGraph, in order:

1. Apply the schema change (or drop/recreate via the regenerated
   `90_drop_all.gsql` + `01_vertices.gsql` + `03_create_graph.gsql` if a clean
   rebuild is acceptable — **drop deletes data**).
2. Reinstall **GQ-004** (`GQ-004_get_driver_causes.gsql`) — its whole-vertex PRINT
   only carries the new attributes after the schema change.
3. Reload the driver_cause seed via the ingestion screen (or full reload): the CSV now
   has 9 columns and **17 rows** (DEAL_SIZE added). `ColumnMismatchError` aborting the
   load means a stale CSV or manifest — regenerate with `build_real_data.py`, do not
   hand-patch.

## 2. Reseed check — names flow from data

After reload, the glossary ("What do these mean?"), driver tags, evidence labels and
exports must show:
- **CLAWBACK → "Charge Back"** (cause_id unchanged),
- **DEAL_SIZE → "Average Transaction Value"** with description and computation (it
  showed a raw id before this round).

Then prove the operator-rename path end-to-end on live data: change one
`display_name` on the vertex (or seed CSV + reload), refresh the UI, confirm the name
changes **everywhere** with no deploy.

## 3. Real-data rebuild + baseline label on April→May

Run `scripts/build_real_data.py` against the real extracts, then the Regenerate
workflow. Confirm:
- The build summary prints April→May per advisor tagged
  `[baseline — indicative attribution]`, **not** as a MIX failure.
- On AI-Insights the April→May transition shows the BASELINE tag + amber note on the
  card, walk row, chart pill and evidence modal — and is **visible**, not hidden.
- MIX on later transitions lands in the expected 0.1–2.3% band (the DEAL_SIZE fix);
  a large later-transition MIX is a real defect, not baseline noise.
- No `UNEXPLAINED_RESIDUAL` anomaly fires on April→May; the rule still fires on
  later transitions if genuinely breached.

## 4. Account comparison against client expectations

Open a NEW_ACCOUNT / LOST_ACCOUNT driver's evidence on real data: the two ranked
lists must show the client's actual account numbers with per-month revenue, the
stated rule ("no activity for 2 consecutive months, ACCOUNT_ABSENCE_MONTHS=2,
advisor level, recurring product lines"), a top-20 cap with "showing N of M", and the
Transactions link must open those exact accounts. This is the client's "top 20
accounts causing the difference" ask — have them validate a couple of accounts.

## 5. Commentary quality on real data

v1.1 prompt: baseline commentary must open with the data-limitation statement and
never narrate April→May account movement as business events. The new guardrail
blocks any narrative that wraps a positive figure in parentheses (parens mean
negative); a BLOCKED transition displays its reason — regenerate for a fresh
version rather than editing stored text.

## 6. Open item — client's revised driver specification (do NOT implement yet)

Recorded in SOLUTION_GUIDE §10.13: the client's eight-driver list, "ineligible =
anything starting with 9", broader recurring set, chargebacks limited to
Annuities/Life. It **conflicts with the CWM PCR Confluence mapping** the build
follows. Needs a reconciliation decision with the client before any code changes.
