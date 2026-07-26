# FIX SPEC — iPerform V2, Round 16 · CRITICAL: PER-ADVISOR VERSION/SCAN PRIMARY-KEY COLLISION

> **CRITICAL — core functionality is broken.** Two screens (AI Insights commentary, Anomalies)
> show nothing after a "generate all" / "rescan all" because of a primary-key collision. Read
> completely. CLAUDE.md §0, §0.1, §3, rule 8a apply. Do not regress rounds 9–15.
> Reconciliation untouched ($0.00) — this is persistence-key plumbing, no figure changes.

---

## THE BUG (root-caused from schema + code, not guessed)

**Commentary versions:** `phx_dm_v2_commentary_version` has `PRIMARY_ID version_id`, and the
workflow builds `version_id = f"v{version_no}"` (generation_workflow.py ~line 227). `version_no`
is a GLOBAL sequence. In a "generate all" run, multiple advisors receive the SAME `version_id`
("v1", "v2", …). Because `version_id` is the primary key, **each advisor's version-vertex upsert
OVERWRITES the previous advisor's** — the LAST advisor (e.g. Z166924) wins. Every other advisor
has commentary ROWS (whose ids include the advisor: `v1|ADVISOR|from|to`) but **no surviving
version vertex**, so `get_commentary` cannot resolve their version and the UI shows "no
commentary". Confirmed by the operator: only 2 version rows exist, both for the last advisor.

**Anomaly scans:** IDENTICAL bug. `phx_dm_v2_anomaly_scan` has `PRIMARY_ID scan_id`, and
detection.py builds `scan_id = f"scan{n:03d}"` (~line 312) with NO advisor in it. "Rescan all"
makes every advisor share `scan001`/`scan002`/… and each overwrites the last — only the final
advisor's scan survives. Anomalies exist in the graph but don't display per advisor.

**Both are the same root cause: a per-advisor entity whose PRIMARY KEY does not include the
advisor, so concurrent per-advisor writes in a bulk run collide and overwrite.**

### TWO COORDINATED LAYERS — fix BOTH, revert NEITHER

There are two distinct layers, and BOTH must be correct or the screen stays broken:

1. **WRITE (the root cause):** the version/scan primary key omits the advisor → bulk writes
   overwrite → only the last advisor's vertex exists in the graph. This is why the UI is empty
   for other advisors — **their data was never persisted.** (Fixed in §A1 / §B1.)
2. **READ (resolver):** the queries that resolve "the latest version/scan" must resolve it
   **per advisor**. `get_commentary` already had its `SumAccum→MaxAccum` fix applied in an
   earlier patch — **KEEP that fix; do NOT revert it.** It is correct and necessary: without it
   the resolver picks the wrong version even when the data is right. But it was never sufficient
   alone, because the WRITE collision starved it of data. `get_anomalies` (GQ-018) uses the same
   latest-resolution pattern (MaxAccum on started_at) and must likewise resolve the latest scan
   **for the given advisor**, not across all advisors.

**Decision on the earlier GSQL patch:** KEEP the MaxAccum change in `get_commentary`. It is a
genuine read-side correctness fix. Reverting it would reintroduce a latent bug that surfaces the
moment the write collision (this round) is fixed. This round adds the WRITE-key fix (the actual
root cause) plus the per-advisor READ resolution for anomalies to match.

---

## A — FIX COMMENTARY VERSION KEY COLLISION

**A1 — Make the version vertex primary id advisor-scoped so it cannot collide.**
- Change `version_id` construction to include the advisor: `version_id = f"v{version_no}|{advisor_sid}"`.
  (Keep `version_no` and `advisor_sid` as separate attributes on the vertex as today.)
- `version_no` stays a per-advisor sequence: `_latest_version_no` must compute the max
  `version_no` **for THIS advisor only** (advisor_sid == advisor_id, plus legacy global ""), so
  each advisor's versions number independently (advisor A can be v1,v2 while advisor B is v1).
  Do NOT read a global max — that was part of the collision.

**A2 — Update every id that references the version id.** Coordinate so nothing dangles:
- commentary rows: `commentary_id` and `version_id` fields;
- the `commentary_in_version` edge (from commentary to version);
- judge evaluation ids (`{commentary_id}|j1`) and their `version_id`;
- the CLI/UI status payloads (`version_ids`, `versions`) and the `_rewrite_version_csv` new-row
  and supersede predicate.
Grep for every construction/consumer of the version id and update them together.

**A3 — Update the queries to resolve per-advisor. KEEP the existing MaxAccum fix in
`get_commentary` (do NOT revert it — it is correct).**
- `get_commentary(advisor_id, version_id)`: when `version_id==""`, resolve the latest version
  **for that advisor** — max `version_no` among versions where `advisor_sid==advisor_id` (or
  legacy ""), then select commentary rows for that advisor + resolved version. The version id it
  builds to match must use the same advisor-scoped format as A1.
- `get_commentary_versions(advisor_id)`: unchanged filter, but ensure it returns each advisor's
  own versions (it already filters by advisor_sid).
- The **supersede** step (generation_workflow ~line 361 + `_rewrite_version_csv`) must supersede
  only THIS advisor's prior PUBLISHED versions — verify it still does with the new key.

## B — FIX ANOMALY SCAN KEY COLLISION (identical pattern)

**B1 — Make the scan vertex primary id advisor-scoped:** `scan_id = f"scan{n:03d}|{advisor_sid}"`
(keep `advisor_sid` as an attribute). `_next_scan_id` numbers per advisor (max among that
advisor's scans + legacy global ""), not globally.

**B2 — Update every id that references the scan id:** anomaly rows (`anomaly_id` embeds
`scan_id`), the `anomaly_in_scan` edge, `anomaly_for_advisor`, `anomaly_cites_driver`, and the
CLI/UI status payloads.

**B3 — Update `get_anomalies` (GQ-018) / `get_anomaly_scans` to resolve the latest scan PER
ADVISOR.** GQ-018 currently resolves the latest scan by `MaxAccum` on `started_at` ACROSS scans;
it must first filter to the given advisor's scans (advisor_sid == advisor_id, or legacy "") and
resolve the latest among THOSE — otherwise it will still cross advisors even after the write fix.
A scan_id must never be shared across advisors. Mirror exactly how get_commentary resolves the
latest version per advisor, for consistency.

## C — MIGRATION (existing collided data is corrupt)

The live graph already contains collided version/scan vertices (only the last advisor's
survive). After the code fix:
- Document in `docs/ROUND16_ACCEPTANCE.md`: the operator must CLEAR the existing
  `phx_dm_v2_commentary_version`, `phx_dm_v2_commentary`, `phx_dm_v2_anomaly_scan`,
  `phx_dm_v2_anomaly` (and their edges) in the live graph, then re-run **generate-all** and
  **rescan-all**, so every advisor gets a correctly-keyed version/scan.
- Provide the exact GSQL/ingestion steps to clear those vertices (a targeted delete, not a full
  schema drop) in the acceptance doc.
- If the schema primary-id definition itself is unchanged (it's still `version_id STRING` /
  `scan_id STRING` — only the VALUE format changes, not the column), NO schema ALTER is needed —
  confirm this and state it, so the operator doesn't need a schema migration, only a data
  refresh.

## D — WHAT NOT TO DO

- Do not change the per-advisor SCOPE model (R11) — this fixes the KEY so scoping actually works.
- Do not change any computed figure, attribution, taxonomy, or eligibility — reconciliation $0.00.
- Do not alter the vertex schema's primary-id COLUMN (only the value format changes); confirm no
  ALTER is needed.
- Do not regress rounds 9–15 (esp. R11 per-advisor buttons, R14 guardrails, R15 items).

## E — VERIFICATION (fixtures / local; the WHOLE point is the multi-advisor bulk run)

The sample has 3 advisors × 3 transitions — but the bug only appears with MULTIPLE advisors in
ONE bulk run, so the tests MUST exercise generate-all / rescan-all across ALL advisors.

1. **Commentary generate-all — EVERY advisor keeps its version:** run generate-all for all
   sample advisors; assert EACH advisor has its OWN PUBLISHED `commentary_version` vertex with a
   distinct advisor-scoped `version_id`; assert `get_commentary(advisor,"")` returns rows for
   EVERY advisor, not just the last. Count version vertices == number of advisors (× versions
   each), never collapsed to one advisor.
2. **No overwrite:** generate-all twice; each advisor now has 2 versions, the latest PUBLISHED,
   the prior SUPERSEDED — per advisor, independently. No advisor's version is missing.
3. **Anomaly rescan-all — EVERY advisor keeps its scan:** run rescan-all; assert each advisor has
   its own `anomaly_scan` vertex with a distinct advisor-scoped `scan_id`; `get_anomalies(advisor,
   "")` returns that advisor's anomalies for EVERY advisor.
4. **Single-advisor still works and doesn't clobber others:** generate/rescan one advisor; only
   that advisor's version/scan changes; others untouched.
5. **Id references intact:** commentary_in_version / anomaly_in_scan edges, evidence, judge
   evaluations all point at the new advisor-scoped ids; no dangling references.
6. All existing suites pass; reconciliation $0.00; rounds 9–15 intact.

Add `scripts/verify_round16.py` that runs generate-all and rescan-all across the full advisor set
and asserts per-advisor version/scan survival with PASS/FAIL counts ("versions: 3/3 advisors have
their own PUBLISHED version"). Exit non-zero on any failure.

## F — PROGRESS TASKS

| ID | Task |
|----|------|
| W-A1 | commentary version_id advisor-scoped (`v{n}|{advisor}`); version_no per-advisor sequence |
| W-A2 | update all version-id references (commentary rows, edge, evaluations, status payloads, CSV) |
| W-A3 | get_commentary / get_commentary_versions resolve latest PER ADVISOR; supersede per advisor |
| W-B1 | anomaly scan_id advisor-scoped; scan number per-advisor |
| W-B2 | update all scan-id references (anomaly rows, edges, status payloads) |
| W-B3 | get_anomalies / get_anomaly_scans resolve latest scan PER ADVISOR |
| W-C | migration steps in ROUND16_ACCEPTANCE.md (clear collided data, regenerate all); confirm no schema ALTER |
| W-D | scripts/verify_round16.py — multi-advisor generate-all + rescan-all survival, PASS/FAIL counts |
| W-E | docs/ROUND16_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) |

## G — DEFINITION OF DONE

- [ ] After generate-all, EVERY advisor has its own PUBLISHED commentary_version with a distinct
      advisor-scoped version_id; get_commentary returns rows for every advisor (not just the last)
- [ ] After rescan-all, EVERY advisor has its own anomaly_scan; get_anomalies returns per advisor
- [ ] version_no / scan number sequence is PER-ADVISOR; no global sequence causing collisions
- [ ] All version/scan id references updated (rows, edges, evidence, evaluations, payloads, CSV) —
      no dangling references
- [ ] Single-advisor generate/rescan still works and does not clobber other advisors
- [ ] No schema ALTER needed (only the id VALUE format changed) — confirmed and stated
- [ ] Migration steps documented; verify_round16.py passes across the full advisor set
- [ ] All suites pass; reconciliation $0.00; rounds 9–15 intact
- [ ] PROGRESS.md W-tasks DONE; BUILD_REPORT round 16 section; ROUND16_CHANGED_FILES.md produced
