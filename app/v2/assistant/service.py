"""Ask iPerform — the per-turn orchestration (FIX_SPEC_R7).

Order of operations for every user turn (A9 — fixed, non-negotiable):

    user text
      -> guardrails.check_input()          BLOCK / REDACT / PASS   (Z-A10)
      -> intent router (deterministic)                             (Z-A3)
      -> constrained LLM fallback if no rule matched               (Z-A4)
      -> context resolution (question > pinned > inherited > screen > default)
      -> catalogued query execution (AnswerEngine — never computes)
      -> narration (AssistantLLM) under the no-invented-figures guardrail
      -> guardrails.check_output() + numeric validation            (Z-A9)
      -> persist (PII already redacted) + render                   (Z-A1)

The model narrates; it never computes. If the LLM wording fails validation,
the deterministic template (built ONLY from stored figures) is used instead
and the answer is marked non-AI — an unvalidated answer is never displayed.
If even the deterministic text fails, the turn is BLOCKED with an honest
message (A8).
"""
from __future__ import annotations

import json

from app.graph.client import get_graph_client
from app.shared.logging import get_logger
from app.v2.assistant import context as ctx_mod
from app.v2.assistant import llm_fallback
from app.v2.assistant.answers import AnswerData, AnswerEngine
from app.v2.assistant.guardrail_gate import screen_input, screen_output
from app.v2.assistant.providers import AssistantLLM
from app.v2.assistant.router import INTENT_QUERIES, Reference, RoutePlan, route
from app.v2.assistant.store import AssistantStore

_log = get_logger("app.v2.assistant")

_ADVICE_LIMIT = ("I can show what happened and why — recommendations aren't "
                 "something I cover yet.")

_NARRATE_SYSTEM = (
    "You are Ask iPerform, a revenue analytics assistant for a wealth "
    "management firm. Rewrite the DETERMINISTIC ANSWER below into 1-3 clear, "
    "professional sentences. HARD RULES: use ONLY figures that appear in the "
    "FIGURES list, copied VERBATIM in their formatted form (negatives stay in "
    "parentheses). Never compute, estimate, round differently, or add any "
    "number, month, advisor or product not present. No advice or "
    "recommendations. No greetings."
)


class AssistantService:
    def __init__(self) -> None:
        self.graph = get_graph_client()
        self.store = AssistantStore()
        self.llm = AssistantLLM()
        self._ref_bundle: dict | None = None

    # ------------------------------------------------------------ reference

    def _reference(self) -> dict:
        if self._ref_bundle is not None:
            return self._ref_bundle
        def rows(name: str, key: str, params: dict | None = None) -> list[dict]:
            result = self.graph.run_query(name, params or {})
            for obj in result.get("results", []):
                if key in obj:
                    return [r.get("attributes", {}) for r in obj[key]]
            return []

        months = rows("get_months", "months")
        advisors = rows("get_advisors", "advisors")
        causes = rows("get_driver_causes", "causes")
        hierarchy = self.graph.run_query("get_product_hierarchy", {})
        groups: dict[str, str] = {}
        for obj in hierarchy.get("results", []):
            for r in obj.get("groups", []):
                a = r.get("attributes", {})
                groups[str(a.get("group_id") or r.get("v_id"))] = str(a.get("group_name") or "")
        month_ids = sorted(str(m.get("month_id")) for m in months)
        self._ref_bundle = {
            "month_ids": month_ids,
            # month_name is already "June 2026" in the loaded data
            "month_names": {str(m.get("month_id")): str(m.get("month_name"))
                            for m in months},
            "advisor_names": {str(a.get("advisor_sid")): str(a.get("advisor_name") or "")
                              for a in advisors},
            "group_names": groups,
            "cause_names": {str(c.get("cause_id")): str(c.get("cause_name") or "")
                            for c in causes},
        }
        return self._ref_bundle

    def _router_reference(self) -> Reference:
        b = self._reference()
        return Reference(month_ids=b["month_ids"], advisors=b["advisor_names"],
                         groups=b["group_names"], causes=b["cause_names"])

    # ------------------------------------------------------------ the turn

    def ask(self, text: str, conversation_id: str = "", screen: dict | None = None,
            pinned: dict | None = None) -> dict:
        ref = self._reference()

        # ---- A9 step 1: input guardrails BEFORE anything else sees the text
        gate = screen_input(text)
        conversation = (self.store.conversation(conversation_id)
                        if conversation_id else None)
        if conversation is None:
            conversation = self.store.create_conversation(
                title=gate.text[:60] or "New conversation",
                advisor_sid=(screen or {}).get("advisor_sid", ""),
                scope_json=json.dumps(pinned) if pinned else "")

        user_message = self.store.append_message(
            conversation, role="USER", text=gate.text,
            status="BLOCKED" if gate.blocked else "OK",
            guardrail_status=gate.status, guardrail_json=gate.findings_json)

        if gate.blocked:
            # A10: no routing, no context resolution, no model call.
            assistant_message = self.store.append_message(
                conversation, role="ASSISTANT", text=gate.refusal,
                status="BLOCKED", guardrail_status="BLOCKED",
                guardrail_json=gate.findings_json)
            return self._payload(conversation, user_message, assistant_message,
                                 suggestions=[], links=[], ai_generated=False)

        # ---- previous turn's resolved context (inheritance, A4)
        previous, last_intent = self._last_context(conversation)

        # ---- stage 1: deterministic router
        plan: RoutePlan = route(gate.text, self._router_reference(), last_intent)
        fallback_provider = ""
        if not plan.intent and not plan.unloaded_month:
            # ---- stage 2: constrained LLM fallback — selection only, validated
            selection = llm_fallback.select(gate.text, self.llm)
            if selection:
                plan.intent = selection["intent"]
                plan.matched_rule = f"llm-fallback:{selection['query']}"
                fallback_provider = selection.get("provider", "")

        resolved = ctx_mod.resolve(
            entities=plan.entities, screen=screen, previous=previous,
            pinned=pinned, month_ids=ref["month_ids"], intent=plan.intent or "")
        resolved_dict = resolved.as_dict()
        resolved_dict["intent"] = plan.intent
        resolved_dict["chip"] = ctx_mod.chip_label(
            resolved, ref["advisor_names"], self._short_months(), ref["group_names"])
        resolved_dict["pinned"] = bool(pinned)

        # ---- honest non-answers (A7)
        if plan.unloaded_month:
            return self._finish_simple(
                conversation, user_message, resolved_dict, "NO_DATA",
                self._unloaded_text(plan.unloaded_month), gate)
        if not plan.intent:
            return self._finish_simple(
                conversation, user_message, resolved_dict, "OUT_OF_SCOPE",
                "That's outside what I can answer — I answer questions about the "
                "loaded revenue data (revenue, changes, drivers, transactions, "
                "anomalies and stored commentary).", gate)

        # ---- run the audited queries (never computes, never invents a name)
        engine = AnswerEngine(self.graph, ref)
        try:
            answer: AnswerData = engine.build(
                plan.intent, resolved, question=gate.text,
                reference_term=plan.reference_term, compare_sids=plan.compare_sids)
        except KeyError:
            return self._finish_simple(
                conversation, user_message, resolved_dict, "OUT_OF_SCOPE",
                "That's outside what I can answer from the loaded data.", gate)

        if answer.status != "OK":
            status = answer.status if answer.status in ("NO_DATA", "OUT_OF_SCOPE") else "NO_DATA"
            text_out = answer.text or (
                f"I can't answer that from the loaded data ({answer.no_data_reason}). "
                + self._loaded_range_text())
            if plan.advisory:
                text_out = f"{text_out} {_ADVICE_LIMIT}"
            return self._finish_simple(conversation, user_message, resolved_dict,
                                       status, text_out, gate,
                                       queries_run=answer.queries_run)

        # ---- narration under the no-invented-figures guardrail (A8/Z-A9)
        # Advisory turns: the narrator words ONLY the factual part; the single
        # limit statement is appended deterministically below (A6 — one brief
        # limit, never repeated disclaimers).
        narrated = self._narrate(answer, resolved_dict,
                                 "" if plan.advisory else gate.text)
        text_out, ai_generated, provider, model, fallback_from = narrated

        if plan.advisory:
            text_out = f"{text_out} {_ADVICE_LIMIT}"

        # ---- output guardrails (A9): PII surfacing from data etc.
        out_gate = screen_output(text_out, json.dumps(answer.figures))
        guardrail_status, guardrail_json = "PASS", ""
        if out_gate.blocked:
            status = "BLOCKED"
            text_out = out_gate.refusal
            guardrail_status, guardrail_json = "BLOCKED", out_gate.findings_json
            ai_generated = False
        else:
            status = "OK"
            if out_gate.status == "REDACTED":
                text_out = out_gate.text
                guardrail_status, guardrail_json = "REDACTED", out_gate.findings_json
        if gate.status == "REDACTED":
            guardrail_status = "REDACTED"
            guardrail_json = guardrail_json or gate.findings_json

        provider_label = provider or fallback_provider
        if fallback_from:
            provider_label += f" (after {', '.join(fallback_from)} failed)"

        assistant_message = self.store.append_message(
            conversation, role="ASSISTANT", text=text_out,
            resolved_context=resolved_dict,
            queries_run=answer.queries_run,
            figures=answer.figures,
            llm_provider=provider_label if ai_generated or answer.verbatim_stored else
            (provider_label + " (deterministic fallback)" if provider_label else "deterministic"),
            status=status, guardrail_status=guardrail_status,
            guardrail_json=guardrail_json)
        return self._payload(conversation, user_message, assistant_message,
                             suggestions=answer.suggestions, links=answer.links,
                             ai_generated=ai_generated or answer.verbatim_stored,
                             evidence_driver_id=answer.evidence_driver_id,
                             served_by_tier=engine.served_by_tier,
                             redaction_note=gate.note)

    # ------------------------------------------------------------ helpers

    def _narrate(self, answer: AnswerData, resolved: dict, question: str
                 ) -> tuple[str, bool, str, str, list[str]]:
        """Returns (text, ai_generated, provider, model, fallback_from)."""
        from app.guardrails.numeric_validation import validate_anomaly_text

        if answer.verbatim_stored:
            # Stored, versioned commentary — validated at publication, quoted
            # verbatim, never re-narrated (CLAUDE.md §7).
            return answer.text, False, "stored-commentary", "", []

        figures_payload = {f["label"]: [f["value"], f["formatted"]] for f in answer.figures}
        prompt = json.dumps({
            "question": question,
            "context": {k: v for k, v in resolved.items() if k not in ("sources",)},
            "deterministic_answer": answer.text,
            "figures": [{"label": f["label"], "formatted": f["formatted"]}
                        for f in answer.figures],
            "facts": answer.facts,
        }, indent=1)
        result = self.llm.generate(prompt, {"system_prompt": _NARRATE_SYSTEM})
        text = (result.get("text") or "").strip()
        if text:
            check = validate_anomaly_text(figures_payload, {}, [text])
            if check["passed"]:
                return text, True, result["provider"], result["model"], result["fallback_from"]
            _log.warning("assistant narration REJECTED by no-invented-figures guardrail "
                         "(%s) — deterministic fallback used", check["blocked_reason"])
        # deterministic template: built only from stored figures, passes by
        # construction — verified anyway for honesty.
        det = validate_anomaly_text(figures_payload, {}, [answer.text])
        if not det["passed"]:
            _log.error("deterministic answer failed its own figure check: %s",
                       det["blocked_reason"])
        return answer.text, False, result.get("provider", ""), result.get("model", ""), \
            result.get("fallback_from", [])

    def _last_context(self, conversation: dict) -> tuple[dict | None, str]:
        rows = self.store.messages(conversation["conversation_id"])["messages"]
        for r in reversed(rows):
            if str(r.get("role")) == "ASSISTANT" and r.get("resolved_context_json"):
                try:
                    ctx = json.loads(str(r["resolved_context_json"]))
                    return ctx, str(ctx.get("intent") or "")
                except (ValueError, TypeError):
                    return None, ""
        return None, ""

    def _short_months(self) -> dict[str, str]:
        return {mid: name.split()[0][:3] for mid, name in
                self._reference()["month_names"].items()}

    def _loaded_range_text(self) -> str:
        names = self._reference()["month_names"]
        ids = self._reference()["month_ids"]
        if not ids:
            return "No months are loaded."
        return f"I only have {names[ids[0]]}–{names[ids[-1]]} loaded."

    def _unloaded_text(self, unloaded: str) -> str:
        label = unloaded
        if unloaded.startswith("????"):
            import calendar
            label = calendar.month_name[int(unloaded[4:6])]
        elif len(unloaded) == 6:
            import calendar
            label = f"{calendar.month_name[int(unloaded[4:6])]} {unloaded[:4]}"
        return f"I don't have {label} loaded. {self._loaded_range_text()}"

    def _finish_simple(self, conversation: dict, user_message: dict, resolved: dict,
                       status: str, text: str, gate, queries_run: list | None = None) -> dict:
        guardrail_status = "REDACTED" if gate.status == "REDACTED" else "PASS"
        assistant_message = self.store.append_message(
            conversation, role="ASSISTANT", text=text,
            resolved_context=resolved, queries_run=queries_run or [],
            status=status, guardrail_status=guardrail_status,
            guardrail_json=gate.findings_json if guardrail_status != "PASS" else "")
        return self._payload(conversation, user_message, assistant_message,
                             suggestions=[], links=[], ai_generated=False,
                             redaction_note=gate.note)

    def _payload(self, conversation: dict, user_message: dict, assistant_message: dict,
                 *, suggestions: list, links: list, ai_generated: bool,
                 evidence_driver_id: str = "", served_by_tier: int | None = None,
                 redaction_note: str = "") -> dict:
        return {
            "conversation": dict(conversation),
            "user_message": user_message,
            "assistant_message": assistant_message,
            "ai_generated": ai_generated,
            "suggestions": suggestions,
            "links": links,
            "evidence_driver_id": evidence_driver_id,
            "served_by_tier": served_by_tier,
            "redaction_note": redaction_note,
            "provider_chain": self.llm.chain,
        }


def catalog_names_used() -> set[str]:
    """Every query name the assistant can run — verified against the catalog
    by scripts/verify_assistant.py (ABSOLUTE RULE 2: never invent a name)."""
    names = {q for queries in INTENT_QUERIES.values() for q in queries}
    names |= {"get_months", "get_advisors", "get_driver_causes",
              "get_product_hierarchy", "get_reason_codes",
              "get_conversations", "get_conversation_messages"}
    return names
