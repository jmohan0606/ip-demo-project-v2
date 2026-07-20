from __future__ import annotations

SYSTEM_PROMPT = """You are iPerform Insights & Coaching, an enterprise wealth-management AI copilot.
You support Advisors, MDWs, DDWs, Executives and AGP program users.
Be concise, evidence-grounded, compliance-aware and action-oriented.
Never invent customer facts. Use supplied context, graph evidence, feature data, recommendations and knowledge snippets only.
When making recommendations, include why, evidence used, next action and compliance status.
"""


def build_agent_prompt(user_question: str, context_packet: dict | None = None, workflow: str = "assistant") -> list[dict[str, str]]:
    context_text = ""
    if context_packet:
        context_text = context_packet.get("compressed_context", "")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Workflow: {workflow}

User question:
{user_question}

Available context:
{context_text}

Return a concise business answer with:
1. Answer
2. Evidence used
3. Recommended next action
4. Compliance note
""",
        },
    ]


def build_recommendation_prompt(context: dict, recommendation_payload: dict) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Generate advisor coaching language based on this recommendation payload.

Context:
{context}

Recommendation payload:
{recommendation_payload}

Return:
- headline
- explanation
- next_steps
- compliance_note
""",
        },
    ]
