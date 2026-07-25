"""R9 D verification — commentary retry + deterministic fallback.

Fixture-only proof (sample set, local tier, scripted stub LLM — NOT a
real-data or live-model verification):

1. A model output that wraps a POSITIVE figure in parentheses fails the
   guardrail on attempt 1; the retry (fresh generation) succeeds and the
   validated wording publishes. Each failure is logged.
2. A model that produces the bad figure on EVERY attempt exhausts
   COMMENTARY_MAX_ATTEMPTS and the DETERMINISTIC TEMPLATE publishes, marked
   as a fallback — the panel is never empty.
3. The guardrail is never bypassed: the bad figure never appears in the
   final narrative, in either scenario.
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("GRAPH_CLIENT_MODE", "local")
os.environ.setdefault("DATA_SET", "sample")
os.environ.setdefault("LLM_CLIENT_MODE", "mock")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ADVISOR, FROM_M, TO_M = "SMPL001", "202604", "202605"  # total change POSITIVE

PASS = FAIL = 0
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    print(("PASS " if ok else "FAIL "), name, detail if not ok else "")
    if ok:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name}: {detail}")


class StubLLM:
    """Scripted model: `bad_attempts` first generations wrap the POSITIVE
    total change in parentheses (the exact client-env defect); later ones
    return clean wording. Figure-free clean wording passes every check."""

    def __init__(self, bad_attempts: int) -> None:
        self.bad_attempts = bad_attempts
        self.calls = 0
        self.bad_figure = ""

    def generate(self, prompt: str, options: dict | None = None) -> str:
        self.calls += 1
        payload = json.loads(prompt)
        total = str(payload["total_change"])          # e.g. "$25,410.85" (positive)
        if self.calls <= self.bad_attempts:
            self.bad_figure = f"({total})"
            text = (f"Credited revenue changed by {self.bad_figure} between the "
                    "two months, led by managed products.")
        else:
            text = ("Credited revenue rose over the period, led by recurring "
                    "managed-product billing; one-time items partly offset.")
        return json.dumps({"narrative_text": text, "bullet_texts": {}})

    def describe(self) -> dict:
        return {"mode": "stub", "model": "stub-scripted"}


def run_sequence(stub: StubLLM):
    import app.llm.client as llm_client_mod
    from app.agents.nodes.supervisor_agent import SupervisorAgent

    real = llm_client_mod.get_llm_client
    llm_client_mod.get_llm_client = lambda: stub  # type: ignore[assignment]
    try:
        return SupervisorAgent().run_generation_sequence(ADVISOR, FROM_M, TO_M, "vtest")
    finally:
        llm_client_mod.get_llm_client = real


def main() -> int:
    from app.config.settings import get_settings

    max_attempts = int(get_settings().commentary_max_attempts)
    check("COMMENTARY_MAX_ATTEMPTS config present (default 3)", max_attempts == 3,
          str(max_attempts))

    # ---- scenario 1: bad attempt 1, clean attempt 2 -> retry publishes
    print("\n— scenario 1: parenthesised-positive on attempt 1; retry succeeds —")
    stub = StubLLM(bad_attempts=1)
    state = run_sequence(stub)
    attempts = state.context.get("validation_attempts", [])
    validation = state.context.get("validation", {})
    commentary = state.context.get("commentary", {})
    check("attempt 1 FAILED the guardrail (parenthesised positive figure)",
          len(attempts) >= 1 and attempts[0]["passed"] is False
          and "parenthes" in attempts[0]["blocked_reason"].lower(),
          str(attempts[:1]))
    check("retry is a FRESH generation and attempt 2 passes",
          stub.calls == 2 and len(attempts) == 2 and attempts[1]["passed"] is True,
          f"calls={stub.calls} attempts={attempts}")
    check("validated model wording publishes (no fallback used)",
          validation.get("passed") is True and not state.context.get("fallback_reason")
          and not commentary.get("is_fallback"),
          str(validation))
    check("the bad figure is NOT in the final narrative (guardrail never bypassed)",
          stub.bad_figure and stub.bad_figure not in commentary.get("narrative_text", ""),
          stub.bad_figure)

    # ---- scenario 2: bad on every attempt -> deterministic fallback publishes
    print("\n— scenario 2: bad figure on every attempt; deterministic fallback —")
    stub2 = StubLLM(bad_attempts=99)
    state2 = run_sequence(stub2)
    attempts2 = state2.context.get("validation_attempts", [])
    validation2 = state2.context.get("validation", {})
    commentary2 = state2.context.get("commentary", {})
    check(f"all {max_attempts} attempts ran and failed (each logged)",
          stub2.calls == max_attempts and len(attempts2) == max_attempts
          and all(a["passed"] is False for a in attempts2),
          f"calls={stub2.calls} attempts={len(attempts2)}")
    check("deterministic template publishes, marked as fallback",
          validation2.get("passed") is True
          and commentary2.get("is_fallback") is True
          and bool(state2.context.get("fallback_reason")),
          str(state2.context.get("fallback_reason"))[:100])
    check("panel is never empty: fallback narrative + bullets present",
          bool(commentary2.get("narrative_text", "").strip())
          and bool(commentary2.get("bullets")),
          str(commentary2.get("narrative_text"))[:60])
    check("no model wording in the fallback (model field says deterministic-template)",
          "deterministic-template" in str(commentary2.get("model", "")),
          str(commentary2.get("model")))
    check("the bad figure is NOT in the fallback narrative (guardrail never bypassed)",
          stub2.bad_figure and stub2.bad_figure not in commentary2.get("narrative_text", ""),
          stub2.bad_figure)

    print(f"\n{'=' * 60}\n{PASS} passed, {FAIL} failed"
          f"{' — OVERALL PASS' if FAIL == 0 else ''}")
    for f in FAILURES:
        print(" -", f)
    print("\nNOTE: fixture verification with a SCRIPTED stub model over the sample "
          "set / local tier — not a real-data or live-model verification "
          "(docs/ROUND9_ACCEPTANCE.md).")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
