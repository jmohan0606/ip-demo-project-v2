# FIX SPEC — iPerform V2, Round 10 · TAXONOMY, ELIGIBILITY, NEW DRIVERS

> **Read completely before starting.** This is a FOUNDATION round: it changes the
> recurring/non-recurring taxonomy that every driver computes on top of, changes the
> eligibility rule that determines the credited-revenue number itself, and adds two new
> drivers. CLAUDE.md §0, §0.1, §3 and rule 8a still apply.
>
> **Strict internal ordering — do the work-streams in this order, because each depends on the
> previous:** A (taxonomy) → B (eligibility) → C (new drivers) → D (chargeback scope) →
> E (LLM health) → F (glossary/verify). Do not start B until A reconciles; do not start C
> until B reconciles.
>
> **The credited-revenue total WILL change this round** (eligibility rule change). That is
> expected and intended — it is not a regression. Reconciliation ($0.00 per transition) must
> still hold at every step.

---

## CONTEXT — why this round exists

The product taxonomy we built came from a Figma screen that was **wrong**. The client has now
given the correct hierarchy (§A). Separately, the eligibility rule is simplified (§B), two new
drivers are added from the client's driver list (§C), and chargeback scope is corrected (§D).
Round 9's five fixes are done and must not regress.

---

## A — CORRECT THE PRODUCT TAXONOMY (do first; everything sits on this)

The recurring-vs-non-recurring classification is currently wrong. Re-seed it to the EXACT
hierarchy below. **Transcribe verbatim — do not paraphrase, do not infer, do not reorder.**

### A1 — The correct hierarchy (verbatim)

```
RECURRING
  Managed
    Unified Managed Account
    JPMCAP
    Advisory
    Mutual funds advisory portfolio
    Customized bond portfolio
  Trails
    Mutual funds
    Annuities
    MAC
    529
  Cash management
    Money market funds
    Premium Deposits

NON-RECURRING
  Cash management
    Brokered CDs
  Annuities
    Fixed
    Variable
  Mutual funds
  Equities and options
    Equities
    Equity Syndicate
    Options
  Fixed income
    Corporate bonds
    Municipal bonds
    Government bonds
    Fixed Syndicate
    Other
  Structured products
  Insurance
  Lending
    Securities-based lending
    Margin
    Fully Paid Lending
  Referrals and revenue share
    Situational partnership
    Private Bank referral
    Everyday 401K
    Other
    Donor-advised funds
    Defined contribution advisory
```

### A2 — THE CRITICAL NUANCE: the same name appears in BOTH classes

**`Annuities`, `Mutual funds`, and `Cash management` each appear under BOTH recurring and
non-recurring.** Therefore **classification by product-group NAME alone is WRONG** and is
exactly the current bug. A transaction's recurring-vs-non-recurring class must be decided by
its **position in this hierarchy** (its product line / parent path), NOT by a name match.

Worked cases the seeding and mapping MUST get right:
- A `Mutual funds` product under **Trails** → RECURRING.
- A `Mutual funds` product at the **non-recurring top level** → NON-RECURRING.
- An `Annuities` product under **Trails** → RECURRING.
- An `Annuities` product under **non-recurring → Fixed/Variable** → NON-RECURRING.
- `Cash management → Money market funds / Premium Deposits` → RECURRING; `Cash management →
  Brokered CDs` → NON-RECURRING.

If the source data cannot distinguish these by product code / hierarchy path, **STOP and
report it in PROGRESS.md** rather than guessing by name — a wrong classification silently
corrupts every downstream driver. Determine from the real product hierarchy
(`raw_product_hierarchy.csv` / `phx_dm_v2_product`, `_product_group`, `_product_line`) whether
the path is available; the mapping must key on it.

### A3 — What to change
- Re-seed `phx_dm_v2_revenue_class`, `phx_dm_v2_product_line`, `phx_dm_v2_product_group`,
  `phx_dm_v2_product` to reflect the hierarchy in A1, with each product line carrying its
  correct `revenue_class` (RECURRING / NON_RECURRING) per its position.
- Propagate through the full chain (same discipline as R8 A4b): DDL if any attribute changes →
  regenerate `schema_catalog.json` + `load_v2_all.gsql` → manifest → both dataset builders
  (sample + `build_real_data.py`) → both tiers.
- The `is_recurring_class` decision used by attribution must derive from this corrected
  seeding, by hierarchy path — never by a name string.

### A4 — Verify
- Every product line resolves to the correct class per A1.
- The three dual-name cases (Annuities, Mutual funds, Cash management) resolve correctly on
  BOTH sides — build a fixture containing a recurring Annuities product AND a non-recurring
  Annuities product and assert each classifies correctly.
- Reconciliation $0.00 on every transition. The account-presence drivers (recurring-only) now
  gate on the corrected classes.

---

## B — ELIGIBILITY RULE CHANGE (do after A reconciles)

**New rule, replacing the reason-code eligibility currently seeded:**
- **Eligible (credited):** reason code is **NULL, empty, or `__NONE__`**.
- **Ineligible (not credited):** **any reason code starting with `9`** (9E, 9G, 9C, 9S, 94,
  9L, 9R, 91, 92, 98, 99, 9H, 9X, XX, and any other `9…`).
- **Forget the prior Confluence-based split.** `91`, `92`, `9L` — previously treated as
  credited-but-incentive-ineligible — are now **ineligible** like every other `9…` code.

**This changes the credited-revenue total.** It is intended. The three-state model is
CONFIRMED and PRESERVED — do not collapse it:

- **Credited:** reason code NULL / empty / `__NONE__` only.
- **Non-Credited:** every `9…` code EXCEPT the excluded set below (e.g. 9E, 9G, 9C, 9S, 94,
  91, 92, 9L). These count toward **Total Revenue** but not Credited Revenue.
- **Excluded:** the existing reversal/error codes stay excluded exactly as today
  (9R, 98, 99, 9H, 9X, XX). They are OUTSIDE Total Revenue — untouched by this change.

**The ONLY change is that `91`, `92`, `9L` move from Credited to Non-Credited.** The Excluded
bucket and its behaviour are unchanged. Confirm the current excluded set from the existing
seed and keep it as-is; do not move any excluded code into non-credited.

Worked example (one advisor-month):
```
(none) $100,000 → Credited
9E      $8,000  → Non-Credited
91      $5,000  → Non-Credited  (was Credited before this round)
9X      $3,000  → Excluded (outside Total Revenue)

Credited Revenue = $100,000
Non-Credited     = $13,000
Total Revenue    = $113,000   (Credited + Non-Credited; excluded not included)
Excluded         = $3,000     (shown as its own line, outside Total)
```

Update `phx_dm_v2_reason_code.include_in_credited` so only NULL/empty/`__NONE__` are TRUE;
set 91/92/9L to FALSE (non-credited); leave the excluded codes' `eligibility=EXCLUDED`
untouched.

**Data note:** treat a genuinely NULL reason code the same as empty/`__NONE__` — eligible. Make
sure the extract/parse maps a missing reason code to the eligible bucket, not to a spurious
non-credited one.

**B2 — Show the excluded breakdown by reason (small display add).** The evidence
"Credited revenue breakdown" ladder already shows a `less excluded` line. Annotate it with the
reason-code breakdown behind it (which `9…`/excluded codes contributed how much), the same way
the `less non-credited` line already takes an annotation. The reason mix is already in the
driver inputs — this is rendering, not new computation. So the operator can point at the
excluded figure and say exactly which codes (e.g. 9X delete) produced it.

**Verify:** a transaction with no reason code is credited; a `91` transaction is now NOT
credited (it was before); the excluded codes remain excluded and outside Total Revenue; the
`less non-credited` line grows and `= Credited revenue` shrinks; the excluded line shows its
reason breakdown; reconciliation $0.00.

---

## C — TWO NEW DRIVERS (do after B reconciles)

Both are **reclassification** drivers: revenue moving because an account's reason-code status
changed month over month. They require this month's AND last month's reason code per account.

**C0 — Data prerequisite (check FIRST, report if missing).** These drivers need per-account,
per-month reason-code presence. Confirm the monthly account data (or the transaction data
grouped by month) retains reason codes per month so "9G present last month, absent this month"
is computable. If it is not available, implement what is possible and record the gap in
PROGRESS.md and the SOLUTION_GUIDE — do not fabricate.

### C1 — `INHERITANCE` driver (reason code 9G)

**Business meaning:** 9G = Inherited Account. When an account is inherited from another advisor
there is an inheritance period (the client cited ~6 months) during which revenue is treated
differently (the client's illustrative example: a 5% inheritance discount). When that status is
present in one month and not the adjacent month, the associated revenue change is attributable
to inheritance rather than to volume or genuine loss.

**Implementation (no effective date is available in the extract — confirmed):**
- Detect accounts whose rows carry **9G in the from-month but not the to-month, or vice
  versa**, and attribute the associated credited-revenue delta to a new `INHERITANCE` driver.
- **Add a clear code comment** that the business rule is a ~6-month inheritance cooling period,
  and that because the extract carries no inheritance effective date, this driver approximates
  it by 9G presence/absence across adjacent months; when an effective date becomes available
  the calculation should be refined to the true 6-month window. Mark provenance `DERIVED`.
- Seed the cause with `display_name` "Inheritance", a description, and a `computation` string.

### C2 — `HOUSEHOLD` driver (reason code 9E)

**Business meaning:** 9E = Minimum Household Policy (small households). Accounts move in and out
of 9E as household groupings change month over month. An account marked 9E last month but not
this month (or vice versa) is a reclassification that can drive a revenue difference.

**Implementation:**
- Detect accounts with **9E in the from-month but not the to-month, or vice versa**, and
  attribute the associated credited-revenue delta to a new `HOUSEHOLD` driver.
- Distinct from the aggregate `ELIGIBILITY` driver: `HOUSEHOLD` isolates the 9E-reclassification
  portion specifically. Ensure `HOUSEHOLD` and `ELIGIBILITY` do not double-count the same
  dollars — `HOUSEHOLD` claims the 9E-transition portion, `ELIGIBILITY` claims the remainder.
- Provenance `DERIVED`; seed `display_name` "Household", description, computation.

### C3 — Ordering and reconciliation
- **The partition mechanism (get this exactly right).** 9G and 9E are themselves non-credited
  reason codes, so their month-over-month movement is ALREADY part of what the aggregate
  `ELIGIBILITY` driver would claim. INHERITANCE and HOUSEHOLD do not add NEW dollars — they
  CARVE OUT specific reason codes from the eligibility effect. Therefore: compute INHERITANCE
  (9G movement) and HOUSEHOLD (9E movement) FIRST, then compute `ELIGIBILITY` as the
  non-credited movement of ALL OTHER `9…` codes EXCLUDING 9G and 9E. That way the three drivers
  sum to the total eligibility effect with no dollar counted twice.
- Place `INHERITANCE` and `HOUSEHOLD` in the attribution order before the generic `ELIGIBILITY`
  remainder.
- Reconciliation $0.00 must still hold. MIX must not absorb inheritance/household movement.
- **Verify with fixtures:** an account flipping 9G off between months produces an `INHERITANCE`
  driver of the right sign and magnitude; an account flipping 9E produces a `HOUSEHOLD` driver;
  neither is double-counted by ELIGIBILITY; reconciliation $0.00.

---

## D — CHARGEBACK (CLAWBACK) SCOPE

**New rule:** the CLAWBACK / "Charge Back" driver applies **only** to **Annuities**,
**Insurance** (product), and **Life** (product code). For every other product, chargebacks/
reversals are NOT attributed to the CLAWBACK driver.

- **Verify the exact names against the real product hierarchy** (`raw_product_hierarchy.csv` /
  `phx_dm_v2_product`, `_product_group`) before coding — "Insurance" is a product group and
  "Life" is a product code; confirm the actual identifiers and gate on those, not on guessed
  strings. Record the confirmed identifiers in a code comment.
- For products outside this set, reversal dollars are handled by the existing buckets (the
  reversal is real negative revenue and still reconciles) but are **not labelled CLAWBACK**.
- **Verify:** a reversal on an Annuities/Insurance/Life product produces a CLAWBACK driver; a
  reversal on, say, Equities does not; reconciliation $0.00.

---

## E — ENV HEALTH: LLM CONNECTIVITY SECTION

Add an **"LLM connectivity"** section to the Env Health screen so the operator can confirm the
model configuration works BEFORE running commentary (the judge silently 404'd in the client
env; this surfaces it up front).

- One row per configured LLM role: **commentary writer**, **judge**, **assistant** — showing
  its provider/mode (cdao_openai / claude / mock), its resolved model name, and a live
  reachability result: **reachable / model-found / UNAVAILABLE**.
- Use the **cheapest possible check** (a lightweight ping or models-list/deployment lookup) —
  NOT a real generation, so checking costs nothing meaningful.
- The **judge row must specifically flag "model not found in subscription"** (the exact 404
  seen with `gpt-4o-mini`) so a bad `JUDGE_MODEL` shows red here rather than mid-run.
- Read config through the same guarded client the agents use; never print secrets (no API
  keys, no tokens) — show provider and model name only.
- This is a read-only diagnostic; it must not generate, publish, or mutate anything.

---

## F — GLOSSARY, SEEDS, VERIFY

- Seed `display_name`, `description`, `computation`, and a sensible `display_order` for the new
  causes `INHERITANCE` and `HOUSEHOLD` (and confirm `DEAL_SIZE`, `CLAWBACK`→"Charge Back",
  `BASELINE_LIMITED` are still correct from R8).
- Glossary renders in `display_order` (attribution order) — carried from R9 F; ensure the two
  new causes slot into the correct position.
- No driver-name literals in the frontend (grep-verified).

---

## G — WHAT NOT TO DO

- Do not regress round 9's five fixes (one-time/adjustment exclusion, account lists, scoped
  chat, commentary-never-empty, judge honest-unavailable).
- Do not change the VOLUME/DEAL_SIZE decomposition arithmetic or the netting against
  FEE_RATE/BILLABLE_DAYS.
- Do not change the 90-day processing rule or the credited grid-type filter.
- Do not classify recurring-vs-non-recurring by product-group NAME — only by hierarchy path.
- Do not fabricate reason-code history or inheritance dates you do not have — report gaps.
- Do not touch the ingestion or TigerGraph screens.

---

## H — VERIFICATION

You cannot reach TigerGraph or real data. Verify on fixtures + local tier; write operator-only
checks in `docs/ROUND10_ACCEPTANCE.md`; never call a fixture check a real-data check.

Required automated checks:
1. Taxonomy: every product line resolves to the correct class per A1; the three dual-name cases
   (Annuities, Mutual funds, Cash management) classify correctly on BOTH sides.
2. Eligibility: NULL/empty/`__NONE__` credited; every `9…` code not credited; `91` flips from
   credited to non-credited; credited totals move; reconciliation $0.00.
3. Inheritance: a 9G flip produces an `INHERITANCE` driver, right sign/magnitude, not
   double-counted by ELIGIBILITY.
4. Household: a 9E flip produces a `HOUSEHOLD` driver, not double-counted.
5. Chargeback: CLAWBACK only on Annuities/Insurance/Life; not elsewhere.
6. LLM health: each role row shows provider/model and reachable/unavailable; an invalid
   JUDGE_MODEL shows "model not found"; no secrets printed.
7. Glossary in display_order incl. the two new causes.
8. All existing suites pass; reconciliation $0.00; zero console errors; round-9 behaviour
   intact.

## I — PROGRESS TASKS

| ID | Task |
|----|------|
| T-A1 | re-seed taxonomy to the verbatim hierarchy (A1) |
| T-A2 | classify by hierarchy path, not name; dual-name cases correct |
| T-A3 | propagate taxonomy through DDL→catalog→loading→manifest→both builders→both tiers |
| T-B1 | eligibility: NULL/empty/__NONE__ credited; 91/92/9L flip to non-credited; excluded set unchanged |
| T-B2 | evidence: annotate the `less excluded` line with its reason-code breakdown |
| T-C0 | confirm per-month reason-code availability; report gap if missing |
| T-C1 | INHERITANCE driver (9G flip) + 6-month cooling-period code note |
| T-C2 | HOUSEHOLD driver (9E flip), not double-counted with ELIGIBILITY |
| T-C3 | attribution order + reconciliation with new drivers |
| T-D1 | CLAWBACK scoped to Annuities/Insurance/Life (real hierarchy names confirmed) |
| T-E1 | Env Health LLM connectivity section (writer/judge/assistant), cheap ping, no secrets |
| T-F1 | seed + glossary order for INHERITANCE/HOUSEHOLD |
| T-G1 | docs/ROUND10_CHANGED_FILES.md (git-derived, conflict flags, operator-local excluded) |

## J — DEFINITION OF DONE

- [ ] Taxonomy matches A1 verbatim; recurring/non-recurring decided by hierarchy path; the
      three dual-name cases classify correctly on both sides
- [ ] Eligibility: NULL/empty/__NONE__ credited; 91/92/9L now non-credited; excluded codes
      (9R/98/99/9H/9X/XX) unchanged and outside Total Revenue; the `less excluded` evidence line
      shows its reason breakdown; credited totals move as expected; reconciliation $0.00
- [ ] INHERITANCE (9G) and HOUSEHOLD (9E) drivers compute from month-over-month reason-code
      flips, correct sign/magnitude, no double-count with ELIGIBILITY, MIX unaffected
- [ ] CLAWBACK applies only to Annuities/Insurance/Life, confirmed against the real hierarchy
- [ ] Env Health shows LLM connectivity per role with an invalid JUDGE_MODEL flagged, no secrets
- [ ] New causes seeded and glossary ordered; no frontend driver-name literals
- [ ] Round 9's fixes intact; all suites pass; reconciliation $0.00; zero console errors
- [ ] `PROGRESS.md` all T-tasks DONE; `BUILD_REPORT.md` Round 10 section separating
      verified-here from operator-pending; `ROUND10_CHANGED_FILES.md` produced
- [ ] Any data gaps (reason-code history, product-hierarchy path, chargeback identifiers)
      reported in PROGRESS.md rather than guessed
