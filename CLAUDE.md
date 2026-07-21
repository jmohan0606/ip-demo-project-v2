# iPerform V2 — Revenue Trends & AI Commentary
## AUTHORITATIVE BUILD SPEC

> Read this file completely before writing any code. Then read every file listed in
> §2 before starting the phase that needs it. This spec is authoritative: where it
> disagrees with anything in `docs/v1_patterns/` or with existing code, **this spec wins**.

---

## 0. WORKING AGREEMENT — read first

**Run autonomously.** Work continuously in auto mode. Do **not** pause for approval, do
not create natural checkpoints, do not ask "shall I continue?". Run until the Definition
of Done (§9) is met and the build report is written. The human is asleep.

**Use parallel subagents where work is independent** (§8 gives the dependency map).
Subagents may NOT commit, may NOT edit `query_catalog.json`, may NOT edit mock modules,
and may NOT create new GSQL queries — they report "NEW QUERY NEEDED: <what data>" back to
the main thread, which authors it. The main thread owns all schema, query, catalog and
mock authoring, and all commits.

**Commit granularly** — one commit per meaningful unit, clear messages. Never squash.
Never force-push. Work on `main` (this is a fresh repo).

**Write the report as you go** — `BUILD_REPORT.md` at the repo root. If it is not in the
report, it did not happen. See §10.

**Checkpoint your progress after every task** — `PROGRESS.md` at the repo root. This is your
crash-recovery file. See §0.1. Update it *before* starting a task and *after* finishing it,
and commit it. If this session dies, the next one resumes from it.

---

## 0.1 PROGRESS PROTOCOL — read this before you start working

Sessions can die: the machine reboots, the network drops, a run is interrupted. When that
happens the next session must be able to resume **without redoing finished work and without
guessing what state things are in**. `PROGRESS.md` is how.

### On starting ANY session

1. **Does `PROGRESS.md` exist?**
   - **No** → this is a fresh start. Create it from the template below with every task set
     to `TODO`, commit it, then begin at Phase 0.
   - **Yes** → this is a **resume**. Do NOT start from the beginning.
2. Read it fully. Find the first task not marked `DONE`.
3. Run `git log --oneline` and `git status` to see what actually landed. **Git is the truth;
   `PROGRESS.md` is the claim.** If a task says `IN_PROGRESS` but its commit exists and the
   files are correct, mark it `DONE` and move on. If a task says `IN_PROGRESS` and the work
   is half-finished or the tree is dirty, finish or redo *that task only*.
4. Append a line to the Session Log, then continue from the first non-`DONE` task.

### While working

- Set a task to `IN_PROGRESS` **before** you start it, with a timestamp.
- Set it to `DONE` **after** its commit lands, recording the commit hash and a one-line note.
- Commit `PROGRESS.md` with (or immediately after) the task's own commit. An uncommitted
  progress file is useless after a crash.
- If you make a decision that a resuming session would need to know (a deferral, an
  assumption, a workaround), write it under **Decisions** — do not leave it only in your head.

### Status values
`TODO` · `IN_PROGRESS` · `DONE` · `BLOCKED` (with reason) · `SKIPPED` (with reason)

### `PROGRESS.md` template

```markdown
# BUILD PROGRESS — iPerform V2
Last updated: <ISO timestamp>
Current phase: <n>
Resume from: <first non-DONE task id>

## Session log
| # | Started | Ended | Resumed from | Notes |
|---|---------|-------|--------------|-------|
| 1 | ... | ... | fresh start | |

## Tasks
| ID | Phase | Task | Status | Commit | Notes |
|----|-------|------|--------|--------|-------|
| P0-1 | 0 | Repair dangling imports | TODO | | |
| P0-2 | 0 | Replace navigation.ts with V2 nav | TODO | | |
| P0-3 | 0 | Set ports 3001/8001 (4 touchpoints) | TODO | | |
| P0-4 | 0 | Backend + frontend both start clean | TODO | | |
| P1-1 | 1 | 01_vertices.gsql (16 vertices) | TODO | | |
| P1-2 | 1 | 02_edges.gsql (23 edges) | TODO | | |
| P1-3 | 1 | 03_create_graph.gsql + schema_catalog.json | TODO | | |
| P2-1 | 2 | GQ-001..004 reference queries | TODO | | |
| P2-2 | 2 | GQ-005..007 trends queries | TODO | | |
| P2-3 | 2 | GQ-008..010 driver/commentary queries | TODO | | |
| P2-4 | 2 | GQ-011..013 evidence/drill-down queries | TODO | | |
| P2-5 | 2 | GQ-014..015 ops queries | TODO | | |
| P2-6 | 2 | query_catalog.json + install_all + query_cases | TODO | | |
| P2-7 | 2 | Local-tier implementations for all queries | TODO | | |
| P3-1 | 3 | Extraction SQL files | TODO | | |
| P3-2 | 3 | manifest.json + loading jobs | TODO | | |
| P3-3 | 3 | Sample data set (exercises every cause) | TODO | | |
| P3-4 | 3 | Delete capability on client interface (both tiers) | TODO | | |
| P3-5 | 3 | Ingestion screen wired: load/reload/ordered delete | TODO | | |
| P4-1 | 4 | app/v2/revenue — monthly aggregation + MoM | TODO | | |
| P4-2 | 4 | app/v2/drivers — attribution + causes | TODO | | |
| P4-3 | 4 | Reconciliation check | TODO | | |
| P5-1 | 5 | supervisor_agent | TODO | | |
| P5-2 | 5 | revenue_agent | TODO | | |
| P5-3 | 5 | commentary_agent | TODO | | |
| P5-4 | 5 | explainability_agent (evidence) | TODO | | |
| P5-5 | 5 | Guardrails validation (5 checks) | TODO | | |
| P5-6 | 5 | Batch generation workflow + versioning | TODO | | |
| P6-1 | 6 | Shell, V2 nav, design tokens, advisor context bar | TODO | | |
| P6-2 | 6 | Trends pivot (01) | TODO | | |
| P6-3 | 6 | Trends MoM (02) | TODO | | |
| P6-4 | 6 | AI Insights chart + cards (03) | TODO | | |
| P6-5 | 6 | Commentary table (06) | TODO | | |
| P6-6 | 6 | Evidence modal (04) | TODO | | |
| P6-7 | 6 | Transactions drill-down | TODO | | |
| P6-8 | 6 | Ingestion screen (05) | TODO | | |
| P6-9 | 6 | Env health screen | TODO | | |
| P7-1 | 7 | End-to-end verification with sample data | TODO | | |
| P7-2 | 7 | BUILD_REPORT.md complete | TODO | | |

## Decisions
| When | Decision | Why |
|------|----------|-----|

## Blocked / deferred
| Task | Reason | What would unblock it |
|------|--------|----------------------|
```

You may add tasks (e.g. new queries), but do not remove or renumber existing ones — a
resuming session relies on the ids.

---

## 1. MISSION

Build a standalone web application that answers one question for a financial advisor:

> **"What is driving the changes in my month-over-month credited revenue?"**

It shows monthly credited revenue broken down by product hierarchy, computes what drove
each month-over-month change, narrates that in plain business language, and — critically —
can **prove every number** it shows, all the way back to source records and a runnable query.

Built on a TigerGraph temporal graph, FastAPI backend, Next.js frontend. Data is three
months (Apr/May/Jun 2026) for ten advisors, extracted from the client's PostgreSQL.

### In scope
- Revenue by product hierarchy, per month, per advisor
- Month-over-month change in $ and %
- Driver attribution (what caused the change) with cause classification
- AI-generated commentary per transition, pre-generated and versioned
- Full evidence for every driver (source records, arithmetic, lineage, runnable queries)
- Data ingestion screen (load / reload / ordered delete)
- Connectivity & environment health screen
- Advisor-level only

### Explicitly OUT of scope
- Any V1 domain concept: AGP, coaching, CRM, recommendations, peer benchmarking,
  predictions, opportunities, what-if, RAG knowledge, memory timeline, impact ledger
- Region / market / MDW roll-ups (advisor only for now — but do not make roll-up impossible)
- Any ML model training
- Household / client-level analysis

---

## 2. THE SPEC PACK — read these before the phase that needs them

| File | Read before |
|---|---|
| `docs/REUSE_MAP.md` | **Phase 0** — what exists, what to build on, what not to touch |
| `docs/tigergraph/SCHEMA_SPEC.md` | Phase 1 — vertices, edges, attributes |
| `docs/tigergraph/QUERY_SPEC.md` | Phase 2 — every GSQL query + syntax rules |
| `docs/data/EXTRACTION_SPEC.md` | Phase 3 — source SQL → CSV → manifest, driver maths |
| `docs/agents/AGENT_SPEC.md` | Phase 5 — the four agents and their contracts |
| `docs/ui/UI_SPEC.md` + `docs/ui/reference/*.png` | Phase 6 — every screen |
| `docs/ui/DESIGN_TOKENS.md` | Phase 6 — colours, type, spacing |
| `docs/v1_patterns/` | Reference only — patterns, not code to import |

---

## 3. ABSOLUTE RULES — violating any of these fails the build

1. **The LLM narrates; it never computes.** Every number that appears anywhere in the UI
   must come from a deterministic computation over graph data. The language model may only
   turn already-computed drivers into sentences. If a figure appears in commentary that is
   not present in the driver set, that is a defect.

2. **Never invent a query name.** Every `run_query("<name>", …)` must name a query that
   exists in `docs/tigergraph_foundation/tigergraph/queries/query_catalog.json`. If you
   need data no query provides, **create the query properly** (§QUERY_SPEC) — never
   force-fit a wrong one, never fabricate a result.

3. **Every fact carries a provenance flag.** `REAL` (from client data), `DERIVED`
   (computed by us from real data), `ASSUMED` (uses a stated assumption), `DUMMY`
   (placeholder, no real data yet). The API returns it; the UI displays it. **Never render
   a DUMMY or ASSUMED value as though it were real.**

4. **Fallback is logged, never silent.** In real mode, if TigerGraph does not serve a
   query, log a WARNING and fall back to the local store. Never silently substitute.
   If the local store serves while `GRAPH_CLIENT_MODE=real`, the health screen goes **red**.

5. **Commentary is generated once, stored, and retrieved.** Never generate narrative text
   on page load. See §7.

6. **Every driver must have evidence.** A driver without a complete evidence record
   (source records, arithmetic, lineage, query + params + result) must not be published.

7. **Contributions must reconcile.** The sum of a transition's driver contributions must
   equal the transition's total change, within rounding tolerance. If it does not, the
   commentary is blocked and the discrepancy logged.

8. **Negative numbers are shown in parentheses** — `($90,685)`, `(17.7%)` — never with a
   minus sign. Everywhere: charts, tables, commentary, evidence.

8a. **Model-authored language is visibly marked.** Any text a model wrote carries an
   "AI Generated" chip in the UI. Computed figures never carry it — the distinction between
   generated wording and computed numbers must be obvious to a reader at a glance.

9. **Do not touch V1.** Never modify anything under `docs/v1_patterns/`. Never import
   from it.

---

## 4. NAMING

- **Vertices/edges:** `phx_dm_v2_*`, meaningful nouns (`phx_dm_v2_revenue_transaction`,
  not `phx_dm_v2_dailtrade_details`). Never mirror source table names.
- **Queries:** `GQ-0NN_<snake_name>.gsql`, catalogued, numbered from `GQ-001`.
- **Backend V2 code:** lives under `app/v2/`. Do not scatter it into V1 infra packages.
- **Frontend V2 code:** `frontend/components/{trends,ai-insights,evidence}/` and routes
  under `frontend/app/(dashboard)/{trends,ai-insights,transactions}/`.
- Only take the columns the schema needs. Do not carry across all ~130 source columns.

---

## 5. PORTS & ENVIRONMENT

V2 runs alongside V1 in the same Codespace, so it must not collide.

| | V1 | **V2** |
|---|---|---|
| Frontend | 3000 | **3001** |
| Backend | 8000 | **8001** |

Change all four touchpoints:
1. `frontend/package.json` — `"dev": "next dev -p 3001"`, `"start": "next start -p 3001"`
2. `run_local_api.py` / `scripts/run_api.sh` — uvicorn `--port 8001`
3. Frontend API base URL env (`NEXT_PUBLIC_API_BASE_URL=http://localhost:8001`)
4. Backend CORS allow-list must include `http://localhost:3001`

**Modes** (`.env`):
```
GRAPH_CLIENT_MODE=real|local        # real = TigerGraph tier 1, local = SQLite tier 2
LLM_CLIENT_MODE=claude|mock
DATA_SET=sample|real                # which CSV set the ingestion screen loads
COMMENTARY_MODE=stored              # never generate on read
```

---

## 6. TIERS & FALLBACK

Two tiers only (V1's four are unnecessary here):

- **Tier 1 — TigerGraph** via pyTigerGraph (`app/graph/`, already present)
- **Tier 2 — Local store (SQLite)** — implements the *same* `run_query` contract

Both tiers return the identical envelope and result shape:
```python
{"error": False, "results": [...], "mode": "...", "served_by_tier": 1|2}
```
Vertex rows are `{"v_id":…, "v_type":…, "attributes":{…}}` — readers access fields via
`row.get("attributes", {})`. **Local-tier query implementations must return this same
nested shape**, so that verifying against tier 2 genuinely proves tier-1 behaviour.

No Kuzu, no second graph engine, no Neo4j.

---

## 7. COMMENTARY GENERATION & VERSIONING

**Batch, not on-demand.** A workflow job (triggerable from the UI) generates commentary
for every advisor × transition, persists it to the graph with its evidence, and stamps it
with a version. Page loads **retrieve** — they never call the LLM.

- Each run creates a `phx_dm_v2_commentary_version` (version_no, generated_at, model,
  prompt_version, data_snapshot_dt, status).
- Commentary and evidence attach to that version.
- **Regeneration is additive** — a new version; previous versions are never deleted and
  remain queryable.
- The UI has a version selector; default is the latest `PUBLISHED` version.
- If validation (§3.7) fails for a transition, that transition's commentary is marked
  `BLOCKED` in that version, with the reason, and the UI says so plainly.

---

## 8. BUILD PHASES & PARALLELISM

Run phases in order. Within a phase, parallelise where marked.

**Phase 0 — Make it build (serial).**
Read `docs/REUSE_MAP.md`. The baseline was pruned from V1, so some retained files import
deleted modules. Fix all dangling imports, strip V1 nav entries, set ports (§5), get
`uvicorn` and `next dev` both starting cleanly with an empty V2 domain. Commit.

**Phase 1 — Schema (serial).**
Author `01_vertices.gsql`, `02_edges.gsql`, `03_create_graph.gsql` per `SCHEMA_SPEC.md`.
Commit.

**Phase 2 — Queries (serial for authoring, parallel for mocks).**
Author every GQ file + catalog entry + local-tier implementation per `QUERY_SPEC.md`.
Commit per logical group.

**Phase 3 — Extraction & ingestion (serial).**
Per `EXTRACTION_SPEC.md`: extraction SQL, CSV contracts, `manifest.json`, loading jobs,
and the **sample data set** (`data/sample/`) that exercises every driver cause. Wire the
ingestion screen's load / reload / **ordered delete**. Commit.

**Phase 4 — Computation (serial).**
`app/v2/revenue/` (monthly aggregation, MoM change) and `app/v2/drivers/` (attribution,
cause classification, reconciliation). This is pure deterministic Python. Commit.

**Phase 5 — Agents (parallel with Phase 6 UI shell).**
Per `AGENT_SPEC.md`: four agents + guardrails validation + the batch generation workflow
+ evidence assembly. Commit.

**Phase 6 — UI (parallelise per screen after the shell is done).**
Shell/nav/tokens first (serial), then these five in parallel, one subagent each:
Trends pivot · Trends MoM · AI Insights · Transactions drill-down · Evidence modal.
Ingestion and env-health screens are adapted from existing V1 components. Commit per screen.

**Phase 7 — Verification & report (serial).** §9, §10.

---

## 9. DEFINITION OF DONE

- [ ] Backend starts on 8001, frontend on 3001, no import errors, no console errors
- [ ] `DATA_SET=sample` loads end-to-end and every screen renders with real content
- [ ] All GSQL queries exist as files, are catalogued, and have local-tier implementations
      returning the identical shape
- [ ] Every screen matches its reference image in `docs/ui/reference/`
- [ ] Commentary generates in batch, persists, versions, and is retrieved (never live)
- [ ] Every driver has a complete evidence record; the evidence modal shows all five
      sections including the PostgreSQL lineage SQL and the runnable GSQL + result
- [ ] Driver contributions reconcile to the total change for every transition
- [ ] Ingestion screen loads, reloads and deletes in dependency order
- [ ] Env-health screen reports the true serving tier and goes red on mock-in-real-mode
- [ ] Negative values in parentheses everywhere
- [ ] REAL / DERIVED / ASSUMED / DUMMY visible wherever a non-real value is shown
- [ ] `PROGRESS.md` shows every task `DONE` (or `BLOCKED`/`SKIPPED` with a reason)
- [ ] `BUILD_REPORT.md` complete

---

## 10. REQUIRED REPORT — `BUILD_REPORT.md`

**Summary:** what was built, ordered commit list with hashes, parallelisation actually
used, and anything deliberately deferred.

**Per phase:** what was produced, key decisions, and how it was verified.

**Schema:** final vertex/edge inventory with each one's provenance flag.

**Queries:** table of every query — `GQ-### | name | purpose | consumer | tested?`.

**Data provenance:** what is REAL, what is DERIVED (and by what formula), what is
ASSUMED (and what the assumption is), what is DUMMY (and what data would make it real).

**Known gaps:** anything a reviewer or the client must know — especially where the driver
decomposition is incomplete because source data was unavailable.

**Client-machine follow-ups:** what must be installed/run/verified against live TigerGraph
that could not be verified here.

---

## 11. IF YOU ARE BLOCKED

Do not stop and wait. In priority order:
1. Re-read the relevant spec file — the answer is probably there.
2. Choose the option that keeps the **provenance honest** (prefer marking something DUMMY
   and moving on, over inventing data).
3. Record the decision and its rationale in `BUILD_REPORT.md` under "Decisions taken while
   blocked", and continue with the next item.

Never fabricate data to unblock yourself. Never silently substitute a placeholder for a
real value. An honest gap is a good outcome; a hidden fabrication is a failed build.
