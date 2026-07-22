"""commentary_agent — narration (AGENT_SPEC §3). The only LLM-using agent.

The LLM receives the computed drivers as structured JSON and writes ONLY
language: an explanation sentence per bullet and the flowing narrative
paragraph. Every figure it may mention is already computed and formatted by
code; titles, headline and driver metadata are assembled deterministically.
If the LLM output cannot be parsed, deterministic fallback sentences built
from the cause vocabulary are used — figures are never affected either way.
"""
from __future__ import annotations

import json
import re

from app.agents.core.base_agent import BaseAgent
from app.agents.state.agent_state import AgentWorkflowState
from app.v2.format import fmt_money, fmt_money_k, fmt_pct

PROMPT_VERSION = "v1.0"

# Bullets shown per card (UI shows five drivers ranked by impact).
BULLET_COUNT = 5

_SYSTEM_PROMPT = """You write month-over-month revenue commentary for a financial advisor.
You will be given ALREADY-COMPUTED revenue drivers as JSON. Your job is language only:
- Use ONLY figures that appear in the input JSON, copied VERBATIM in their given format (e.g. "($44.1k)", "(17.7%)").
- NEVER introduce, adjust, round, re-round or infer a number. NEVER compute sums, differences, ratios or combined figures across drivers — if you want to describe a combination, use words ("together", "largely offset"), not a new number.
- If a figure is not in the input, it must not appear in your output.
- Negative amounts are written in parentheses, never with a minus sign.
- Use the client's product vocabulary exactly as given in the input.
- A driver flagged data_source DUMMY or ASSUMED must be described as unavailable/placeholder, never as an established fact.
Respond with ONLY a JSON object:
{"narrative_text": "<one flowing paragraph for the transition>",
 "bullet_texts": {"<driver_id>": "<one plain-business-language sentence explaining that driver>"}}"""

_CAUSE_FALLBACK = {
    "VOLUME": "Transaction volume changed at broadly similar rates.",
    "ONE_TIME": "One-time items in one month did not repeat in the other.",
    "ELIGIBILITY": "Revenue moved between credited and non-credited reason codes month over month.",
    "LATE_PROCESSING": "Revenue excluded by the 90-day processing rule changed between the months.",
    "EXCLUDED_CHANGE": "Revenue moved between credited and excluded reason codes (e.g. a deleted booking).",
    "TIMING": "Quarterly billing fell in one month of the pair, not the other.",
    "FEE_RATE": "The effective fee rate on the recurring base moved between the months.",
    "DISCOUNT": "Discounting changed between the months.",
    "BILLABLE_DAYS": "The months have a different number of billable days.",
    "MIX": "The remaining movement reflects shifts between products at different rates.",
    "NEW_ACCOUNT": "Accounts contributed this month that did not contribute last month.",
    "LOST_ACCOUNT": "Accounts that contributed last month did not contribute this month.",
    "CLAWBACK": "Reversal (negative) amounts changed between the months.",
    "MARKET": "Market performance effect is a placeholder — no index-return source is available.",
    "NET_FLOW": "Net client flow effect is a placeholder — the flows feed stops before this period.",
}


def _month_name(month_id: str) -> str:
    names = ["", "January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
    return f"{names[int(month_id[4:6])]} {month_id[:4]}"


def _driver_payload(d: dict) -> dict:
    """What the LLM sees for one driver — figures pre-formatted by code."""
    return {
        "driver_id": d["driver_id"],
        "rank": d["rank"],
        "product_group": d["group_name"],
        "cause": d["cause_id"],
        "direction": d["direction"],
        "contribution": fmt_money_k(d["contribution_amt"]),
        "contribution_exact": fmt_money(d["contribution_amt"]),
        "share_of_change": fmt_pct(d["contribution_pct"]),
        "data_source": d["data_source"],
        "inputs": d.get("inputs") or {},
    }


def build_headline(revenue_output: dict) -> str:
    arrow = "▲" if revenue_output["change_amt"] >= 0 else "▼"
    return (f"{arrow} {fmt_money(revenue_output['change_amt'])}  "
            f"{fmt_pct(revenue_output['change_pct'])}")


def narrate(revenue_output: dict, llm) -> dict:
    """Commentary output contract from the revenue_agent output. `llm` is the
    active LLM client (claude or mock)."""
    top = [d for d in revenue_output["drivers"]][:BULLET_COUNT]
    payload = {
        "transition": f"{_month_name(revenue_output['from_month'])} -> {_month_name(revenue_output['to_month'])}",
        "total_change": fmt_money(revenue_output["change_amt"]),
        "total_change_pct": fmt_pct(revenue_output["change_pct"]),
        "from_revenue": fmt_money(revenue_output["from_revenue"]),
        "to_revenue": fmt_money(revenue_output["to_revenue"]),
        "drivers": [_driver_payload(d) for d in top],
    }
    llm_model = "unavailable"
    narrative = ""
    bullet_texts: dict[str, str] = {}
    try:
        raw = llm.generate(json.dumps(payload, indent=2), {"system_prompt": _SYSTEM_PROMPT})
        llm_model = llm.describe().get("model", llm.describe().get("mode", "unknown"))
        match = re.search(r"\{.*\}", raw or "", re.S)
        if match:
            parsed = json.loads(match.group(0))
            narrative = str(parsed.get("narrative_text") or "")
            bullet_texts = {str(k): str(v) for k, v in (parsed.get("bullet_texts") or {}).items()}
    except Exception:  # noqa: BLE001 — deterministic fallback below; never fabricates figures
        pass

    if not narrative:
        llm_model = f"{llm_model} (deterministic fallback)"
        direction = "up" if revenue_output["change_amt"] >= 0 else "down"
        parts = [
            f"Credited revenue moved {direction} {fmt_money(revenue_output['change_amt'])} "
            f"({fmt_pct(revenue_output['change_pct'])[1:-1] if revenue_output['change_pct'] < 0 else fmt_pct(revenue_output['change_pct'])}) "
            f"from {_month_name(revenue_output['from_month'])} to {_month_name(revenue_output['to_month'])}."
        ]
        for d in top[:3]:
            parts.append(f"{d['group_name']} contributed {fmt_money_k(d['contribution_amt'])} "
                         f"({_CAUSE_FALLBACK.get(d['cause_id'], d['cause_id']).lower().rstrip('.')}).")
        narrative = " ".join(parts)

    bullets = []
    for d in top:
        bullets.append({
            "driver_id": d["driver_id"],
            "direction": d["direction"],
            # "Structured Products ($44.1k)" — the parentheses ARE the sign (rule 8);
            # positive contributions read "Managed $12.3k".
            "title": f"{d['group_name']} {fmt_money_k(d['contribution_amt'])}",
            "text": bullet_texts.get(d["driver_id"]) or _CAUSE_FALLBACK.get(d["cause_id"], ""),
            "cause_id": d["cause_id"],
            "group_id": d["group_id"],
            "data_source": d["data_source"],
        })
    return {
        "headline": build_headline(revenue_output),
        "narrative_text": narrative,
        "bullets": bullets,
        "model": llm_model,
        "prompt_version": PROMPT_VERSION,
    }


class CommentaryAgent(BaseAgent):
    name = "commentary_agent"
    description = "Narrates already-computed drivers into commentary. Language only — never computes."

    def run(self, state: AgentWorkflowState) -> AgentWorkflowState:
        from app.llm.client import get_llm_client

        task = self.create_task("narrate computed drivers")
        try:
            revenue_output = state.context["revenue_output"]
            state.context["commentary"] = narrate(revenue_output, get_llm_client())
            state.tasks.append(self.complete_task(task, {"bullets": len(state.context["commentary"]["bullets"])}))
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"commentary_agent: {exc}")
            state.tasks.append(self.fail_task(task, exc))
        return state
