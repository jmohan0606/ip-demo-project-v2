# ROUND 10 ACCEPTANCE — operator-only checks

Everything verifiable on the build box (fixtures + sample data + local tier)
has been verified and is recorded in `BUILD_REPORT.md` §16. The checks below
require the client machine (live TigerGraph, the real extracts, the cdao
subscription) and CANNOT be verified here. None of the fixture results should
be read as a real-data verification.

## 1. Taxonomy against the REAL product hierarchy

The corrected A1 hierarchy is seeded and classification keys on the
`(level_one_product, level_two_product)` PATH — proven on fixtures only.

1. Re-run `extract_product_hierarchy.sql`, save `raw_product_hierarchy.csv`.
2. `python -m scripts.build_real_data`
3. **Expect:** the build completes; any hierarchy path A1 does not know is
   either created under its known line, or — for the dual-name lines
   (Annuities / Mutual funds / Cash management) — STOPS the build with the
   exact ambiguous paths printed. A STOP means the extract's group names do
   not pin down the recurring side: extend `app/v2/revenue/taxonomy.py` with
   the client, never guess by name.
4. **Expect:** any `WARNING — product lines NOT in the corrected client
   hierarchy` lists only lines the client confirms are non-recurring.
5. Reload via the ingestion screen; the Trends pivot shows the A1 lines
   (Cash management appears under BOTH classes when both sides have revenue).

## 2. Eligibility totals on real data

The credited-revenue total CHANGES this round (91/92/9L flip to
non-credited). Confirm with the client that the new credited totals match
iComp expectations for a known advisor/month. The evidence ladder's
`less non-credited` line grows accordingly; `less excluded` now shows its
reason-code breakdown (e.g. `9X … ×n`).

## 3. INHERITANCE / HOUSEHOLD on real data

Both drivers approximate reclassification by 9G/9E presence/absence across
adjacent months (no inheritance effective date exists in the extract). On the
client build, pick an account known to have finished its inheritance period
and confirm the INHERITANCE driver carries the expected sign/magnitude. When
an inheritance effective-date field becomes available, refine the driver to
the true ~6-month window (code note in `app/v2/drivers/attribution.py` §3a-1).

## 4. CLAWBACK identifiers

The Annuities/Insurance scope is confirmed against the A1 hierarchy. The
**Life product-code gate is ASSUMED to be `product_cd == "LIFE"`** — verify
the real code value in `raw_product_hierarchy.csv` / `phx_dm_v2_product` and
correct `CLAWBACK_PRODUCT_CODES` in `app/v2/revenue/taxonomy.py` if it
differs.

## 5. LLM connectivity on the client env

Open Env Health with `LLM_CLIENT_MODE=cdao_openai`:

- three rows (commentary writer / judge / assistant) show provider + resolved
  model; the check is a models lookup — no generation is billed.
- Set `JUDGE_MODEL` to the known-bad `gpt-4o-mini`: the judge row must go
  **UNAVAILABLE — model not found in subscription** (verified live on the
  build box against the Anthropic API; the cdao path needs the client env).
- Confirm no key/token text appears anywhere on the screen.

## 6. Live reinstall / reseed

Unchanged DDL this round, but the DATA seeds changed. On the client machine:
re-run the loading job for `phx_dm_v2_revenue_class`, `_product_line`,
`_product_group`, `_product`, `_reason_code`, `_driver_cause` (or a full
reload), then regenerate commentary (new version; prior versions remain).
