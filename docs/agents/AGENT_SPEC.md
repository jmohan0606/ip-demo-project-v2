# AGENT SPEC — iPerform V2

Four agents. Three reuse V1's names and roles so that when V1 goes to production there is no
conflicting implementation to reconcile — `revenue_agent` and `explainability_agent` simply
gain V2 capabilities.

Built on the existing framework: `app/agents/core/base_agent.py`,
`app/agents/state/agent_state.py`, `app/agents/registry/`. Nodes go in `app/agents/nodes/`.

---

## THE GOVERNING RULE

> **The language model narrates. It never computes.**

Every number shown anywhere in the app is produced by deterministic Python over graph data.
The LLM receives already-computed drivers and turns them into sentences. It may choose
wording, ordering emphasis and phrasing. It may not produce, adjust, round or infer a
figure. Guardrails enforce this mechanically (§5) — it is not left to prompt discipline.

---

## 1. `supervisor_agent` — orchestration *(V1 name, V1 role)*

Routes a request, sequences the others, assembles the response. Two workflows:

**A. Commentary generation (batch, offline)** — for each advisor × transition:
`revenue_agent` → `commentary_agent` → guardrails validation → `explainability_agent` →
persist under a new version. Parallelise across advisors; serialise within an advisor.

**B. Read (online)** — retrieval only. Fetch stored commentary + evidence via
`run_query`. **Must never invoke `commentary_agent`.** If commentary is missing for a
transition, return an empty state telling the user to run generation — do not generate.

Routing rules stay declarative (V1's `ROUTING_RULES` pattern) so the topology can be
rendered if an agent-map view is ever added.

---

## 2. `revenue_agent` — metrics + attribution *(V1 name, extended)*

**Fully deterministic. No LLM. No randomness.**

Given `(advisor_id, from_month, to_month)`:
1. Monthly revenue by product group (GQ-005) and totals (GQ-006)
2. MoM change $ and % at total and group level (GQ-007)
3. Driver attribution per `EXTRACTION_SPEC §7`, classified by cause
4. Reconciliation check: `Σ contributions == change_amt` (±$1)
5. Rank by `|contribution|`; capture `inputs_json` for every driver

Implementation lives in `app/v2/revenue/` and `app/v2/drivers/`; the agent is a thin node
over it, so the same code is callable outside the agent framework.

**Output contract**
```python
{
  "advisor_id": "V236209", "from_month": "202605", "to_month": "202606",
  "from_revenue": 512340.00, "to_revenue": 421655.00,
  "change_amt": -90685.00, "change_pct": -17.7,
  "txn_count": 5948,
  "reconciled": True, "residual": 0.00,
  "drivers": [
    {"driver_id":"…","rank":1,"group_id":"structured-products","group_name":"Structured Products",
     "cause_id":"ONE_TIME","contribution_amt":-44100.00,"contribution_pct":48.6,
     "direction":"DOWN","data_source":"REAL",
     "inputs":{"from_revenue":52400.00,"to_revenue":8300.00,"from_txn_count":31,"to_txn_count":18,
               "components":[{"label":"Syndicate allocations (one-time)","from":31200.00,"to":0.00}]}}
  ]
}
```

---

## 3. `commentary_agent` — narration *(NEW — the only new agent)*

The only LLM-using agent. Input is `revenue_agent`'s output; output is language.

**Prompt contract**
- System prompt states: you will be given computed drivers; write commentary using **only**
  those figures; never introduce, adjust or infer a number; if a figure is not in the input,
  it may not appear in the output.
- Input is the driver list as structured JSON.
- Use the client's vocabulary: Managed, Trails, Structured Products, Alternative
  Investments, Fixed Income, Equities and Options, Mutual Funds, Cash Management, Lending,
  Insurance, Referrals and Revenue Share, Defined Contribution Advisory, Donor Advised Funds.
- Negatives in parentheses: `($44.1k)`, `(17.7%)`.
- Every bullet carries its `driver_id` so the UI can deep-link to evidence.

**Output contract**
```python
{
  "headline": "($90,685)   (17.7%)",
  "narrative_text": "MoM down ~$91k, driven primarily by the absence of one-time and quarterly items …",
  "bullets": [
    {"driver_id":"…","direction":"DOWN","title":"Structured Products ($44.1k)",
     "text":"No new note issuance in June; May's one-time syndicate allocations did not repeat.",
     "cause_id":"ONE_TIME","group_id":"structured-products","data_source":"REAL"}
  ]
}
```

Two forms, both from the same drivers: **bullets** for the AI Insights cards, and
**`narrative_text`** — one flowing paragraph — for the commentary table (mockup 06).

Set `prompt_version` explicitly and store it on the version record; when the prompt changes,
the version number changes.

---

## 4. `explainability_agent` — evidence *(V1 name, V1 role)*

Assembles a complete `phx_dm_v2_evidence` record per driver. **No LLM** except optionally
the one-sentence `finding_text`, which must restate only figures already present.

Produces the five sections of the evidence modal:
1. **finding_text** — what happened and why, in one or two sentences
2. **calc_json** — component rows (label, from, to, change, share) + the formula string
3. **source_records_json** — sample transactions (trade_ref, date, product, account, type,
   credited, split %) + total contributing count
4. **lineage_json** — vertex path with match counts · **checks_json** — the automated checks
   and their pass/fail
5. **gsql_query_name / gsql_params_json / gsql_result_json** — the query that was actually
   run and what it returned · **source_sql / source_table / source_row_count** — the
   PostgreSQL extraction SQL, *lineage only, not executed*

**A driver with no evidence record must not be published.**

---

## 5. VALIDATION — guardrails, not an agent

Lives in the existing `app/guardrails/` module, called by `supervisor_agent` between
`commentary_agent` and `explainability_agent`. Deliberately not an agent: it is a
deterministic gate, and this keeps the roster at four.

Checks, all blocking:
1. **No invented figures.** Extract every number from `narrative_text` and every bullet;
   each must match a value in the driver set (within rounding). Any orphan → **BLOCK**.
2. **Reconciliation.** `Σ contributions == change_amt` (±$1) → else **BLOCK**.
3. **Evidence completeness.** Every cited `driver_id` resolves to a driver with an evidence
   record → else **BLOCK**.
4. **Provenance honesty.** Any bullet citing a `DUMMY`/`ASSUMED` driver must be flagged as
   such in its `data_source`; it may not read as established fact.
5. **Format.** Negatives parenthesised; no minus signs in displayed figures.

On block: mark that transition's commentary `BLOCKED` with `blocked_reason`, persist it
(don't discard — the blockage is diagnostic), continue with other transitions. The UI shows
blocked transitions plainly rather than silently omitting them.

---

## 6. GENERATION WORKFLOW

`app/v2/commentary/generation_workflow.py`, triggered from the UI or CLI.

1. Create a `phx_dm_v2_commentary_version` (`status=DRAFT`, model, prompt_version,
   data_snapshot_dt)
2. For each advisor × transition (parallel across advisors):
   `revenue_agent` → `commentary_agent` → guardrails → `explainability_agent` → persist
3. Persist commentary + evidence attached to that version
4. Set `status=PUBLISHED`, record `blocked_count`; mark the prior version `SUPERSEDED`
5. **Never delete a previous version**

Idempotent: re-running creates a *new* version, never mutates an existing one.

---

## 7. WHAT NOT TO BUILD

No agents for: prediction, recommendation, opportunity, coaching, compliance, RAG /
knowledge retrieval, memory, feedback learning, peer benchmarking. All V1 concepts, all out
of scope. Four agents. If you think you need a fifth, you almost certainly need a function.
