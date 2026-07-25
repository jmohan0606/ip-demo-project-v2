# ROUND 11 — OPERATOR ACCEPTANCE (client machine only)

Everything below could NOT be verified in the build environment (no TigerGraph,
no real data, no cdao endpoint). Everything else in FIX_SPEC_R11 was verified
here on fixtures + the local tier + the sample set — see `BUILD_REPORT.md` §17.

## 1. Live query reinstall (required — four queries changed)

`GQ-009`, `GQ-010`, `GQ-018`, `GQ-019` changed for per-advisor versions/scans,
and the schema gained `advisor_sid` on `phx_dm_v2_commentary_version` and
`phx_dm_v2_anomaly_scan`.

1. Re-run the schema DDL (attribute additions require the drop/recreate
   procedure in SOLUTION_GUIDE ch.9 / `90_drop_all.gsql`) or apply the two
   `ADD ATTRIBUTE` changes per your TigerGraph version's alter path.
2. Reinstall the four queries (`install_all_queries.gsql` covers them).
3. Reload data (the loading job + manifest now carry `advisor_sid` columns;
   legacy rows load with an empty value and are treated as "legacy global").

## 2. Real-hierarchy taxonomy check (A)

Run `scripts/build_real_data.py` against the real extracts and confirm on its
summary:
- every `grid_type = PRODUCT_TYPE` path classifies with NO stop;
- `Alternative Investments` (ALTI) lands NON_RECURRING — **this class is an
  ASSUMPTION pending client confirmation**; confirm it with the client and, if
  they place it under recurring, edit `app/v2/revenue/taxonomy.py` (comment
  marks the spot) and rebuild;
- the NON_CREDITED_REVENUE / PAY_TYPE_SUMMARY rows are listed under the
  "excluded from taxonomy classification" INFO block, never as product lines;
- reconciliation $0.00.

## 3. Per-advisor scope on real data (B)

1. On AI Insights pick one advisor → **Regenerate (this advisor)**. Confirm:
   a new version appears only in that advisor's selector; switching to any
   other advisor still shows their previous latest version; figures unchanged.
2. **Regenerate all** → every advisor gets its OWN new version (check the
   selector shows `advisor_sid`-scoped entries, not one global version).
3. Repeat 1–2 with Rescan on the Anomalies screen.

## 4. Async + overlay under real latency (C)

With ~10 advisors a Regenerate-all takes real time — confirm: the overlay
shows "advisor N of M" and advances; closing the tab mid-run and reopening
rejoins the same job; on completion the screen selects the new version without
a manual reload; a forced failure (e.g. wrong ANTHROPIC key) surfaces the
reason in the overlay instead of dismissing silently.

## 5. LLM connectivity pre-flight (E)

Before the first long Regenerate-all, open Env Health and confirm the three
LLM rows (writer / judge / assistant) show `model-found` against the cdao
endpoint. A judge 404 must read "model not found in subscription".

## 6. Sample-demo check (D — optional but recommended)

With `DATA_SET=sample`: Rescan-all must flag all six anomaly rules (the
crafted stories are per-advisor: SMPL001 LARGE_SWING + FEE_RATE_SHIFT,
SMPL002 UNEXPLAINED_RESIDUAL, SMPL003 CLAWBACK_CONCENTRATION), and the
commentary walk must show INHERITANCE / HOUSEHOLD / CLAWBACK drivers.
SMPL002 Jun→Jul is deliberately high-residual; every other transition is
MIX-clean.
