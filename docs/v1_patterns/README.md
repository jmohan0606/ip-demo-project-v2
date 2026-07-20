# V1 Pattern References — READ ONLY

These files are **examples of patterns**, copied from the V1 codebase. They exist so you
can see how a thing was done that worked. They are NOT part of the V2 application.

RULES
1. **Do not import from this folder.** Nothing here is on the Python path.
2. **Do not copy these files wholesale** into `app/`. Copy the *pattern*, write V2 code.
3. **The spec pack wins.** Where these examples and `/CLAUDE.md` or `docs/**/*_SPEC.md`
   disagree, the spec is authoritative. These files may be stale.
4. V1 domain concepts (advisors' AGP, coaching, CRM, recommendations, peers, predictions)
   are **out of scope for V2**. Ignore them if you see them referenced here.

| File | Shows you |
|---|---|
| `EXAMPLE_reader_run_query.py` | A service reading the graph via `run_query` with a **logged** fallback, never silent |
| `EXAMPLE_query_helpers.py` | `run_catalog_query()` — the error/served-by-tier logging contract |
| `EXAMPLE_mock_query_impls.py` | `@mock_query` implementations returning the **real vset shape** `{v_id, v_type, attributes:{...}}` |
| `EXAMPLE_query.gsql` | A GSQL query in the **V1 syntax** that installs on TigerGraph 4.2.x |
| `EXAMPLE_query_catalog.json` | Catalog entry format |
| `EXAMPLE_work_report.md` | The report format expected at the end of a build run |
