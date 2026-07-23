"""Stage-2 routing fallback (FIX_SPEC_R7 A3): a CONSTRAINED selection, never
an answer.

Only reached when the deterministic router matched nothing. The model is
given ONLY the catalogued query list with their parameters and must return a
structured {"query", "params", "intent"} selection — not prose, not a figure.
The selection is validated against query_catalog.json before anything runs;
an invalid or unmappable selection yields None and the assistant returns the
honest "outside what I can answer" response (A6/A7). The model never answers
from its own knowledge.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.shared.logging import get_logger
from app.v2.assistant.router import INTENT_QUERIES

_log = get_logger("app.v2.assistant.fallback")

_CATALOG_PATH = Path("docs/tigergraph_foundation/tigergraph/queries/query_catalog.json")

# Queries the fallback may select — the read-only analytical set. Persistence
# and ops queries are excluded on purpose.
_SELECTABLE = sorted({q for names in INTENT_QUERIES.values() for q in names})


@lru_cache(maxsize=1)
def catalog_queries() -> dict[str, dict]:
    catalog = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return {q["name"]: q for q in catalog.get("queries", [])}


def _prompt(question: str) -> tuple[str, dict]:
    lines = []
    for name in _SELECTABLE:
        spec = catalog_queries().get(name)
        if not spec:
            continue
        params = ", ".join(f'{p["name"]}:{p["type"]}' for p in spec.get("parameters", []))
        lines.append(f'- {name}({params}) — {spec.get("purpose", "")}')
    intents = ", ".join(sorted(INTENT_QUERIES))
    prompt = (
        "You are a query selector for a revenue analytics assistant. "
        "Map the user's question to EXACTLY ONE query from the catalog below. "
        "Respond with ONLY a JSON object — no prose:\n"
        '{"intent": "<one of: ' + intents + '>", "query": "<query name>", "params": {}}\n'
        'If the question cannot be answered by any catalogued query, respond {"query": null}.\n'
        "NEVER answer the question yourself. NEVER include figures or facts.\n\n"
        "Catalog:\n" + "\n".join(lines) + "\n\nQuestion: " + question
    )
    context = {"system_prompt":
               "You select queries from a fixed catalog. You output only JSON. "
               "You never answer questions directly and never produce figures."}
    return prompt, context


def select(question: str, llm) -> dict | None:
    """Returns a validated {"intent", "query", "params", "provider"} or None."""
    prompt, context = _prompt(question)
    result = llm.generate(prompt, context)
    text = result.get("text") or ""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        _log.info("fallback selector returned no JSON — OUT_OF_SCOPE")
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        _log.warning("fallback selector returned unparseable JSON — OUT_OF_SCOPE")
        return None
    query = parsed.get("query")
    if not query or not isinstance(query, str):
        return None
    if query not in _SELECTABLE or query not in catalog_queries():
        _log.warning("fallback selected a non-catalogued/non-selectable query %r — rejected", query)
        return None
    declared = {p["name"] for p in catalog_queries()[query].get("parameters", [])}
    params = parsed.get("params") or {}
    if not isinstance(params, dict) or any(k not in declared for k in params):
        _log.warning("fallback selection for %s carried undeclared params — rejected", query)
        return None
    intent = str(parsed.get("intent") or "")
    if intent not in INTENT_QUERIES:
        intent = next((i for i, names in INTENT_QUERIES.items() if query in names), "")
        if not intent:
            return None
    _log.info("fallback selector mapped question to %s via %s", intent,
              result.get("provider"))
    return {"intent": intent, "query": query, "params": params,
            "provider": result.get("provider", ""),
            "fallback_from": result.get("fallback_from", [])}
