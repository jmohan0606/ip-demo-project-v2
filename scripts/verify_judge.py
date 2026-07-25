"""R9 E verification — judge on the standard adapter, honest unavailable state.

Fixture-only proof (stubs + config objects — NOT a live-model check):
1. The judge client comes from the SAME multi-mode adapter factory the agents
   use (build_llm_client), with JUDGE_MODEL selecting the model in the active
   mode (empty = mode default; claude mode keeps the R5 claude-sonnet-5).
2. When the judge cannot run (mock mode, or the model call fails — the
   client-env 404), scores carry the -1.0 UNAVAILABLE sentinel and the
   reasoning says "Judge unavailable — human review recommended". NEVER 0.00.
3. The judge is advisory only: its result never feeds the publication gate
   (status comes from the deterministic guardrail validation alone).
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("GRAPH_CLIENT_MODE", "local")
os.environ.setdefault("DATA_SET", "sample")
os.environ.setdefault("LLM_CLIENT_MODE", "mock")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


REVENUE_OUTPUT = {
    "from_month": "202604", "to_month": "202605",
    "change_amt": 100.0, "change_pct": 1.0,
    "from_revenue": 10000.0, "to_revenue": 10100.0,
    "drivers": [],
}
COMMENTARY = {"headline": "▲ $100.00  1.0%", "narrative_text": "Revenue rose.",
              "bullets": []}


class Erroring404LLM:
    """Simulates the client-env failure: Deployment not found (404)."""

    def generate(self, prompt: str, options: dict | None = None) -> str:
        raise RuntimeError("Deployment 'gpt-4o-mini' not found in configuration "
                           "mapping for this subscription (404)")

    def describe(self) -> dict:
        return {"mode": "cdao_openai", "model": "cdao:gpt-4o-mini"}


class GoodJudgeLLM:
    def generate(self, prompt: str, options: dict | None = None) -> str:
        return ('{"faithfulness_score": 0.9, "hallucination_flag": false, '
                '"completeness_score": 0.8, "clarity_score": 0.85, '
                '"verdict": "PASS", "reasoning": "Consistent with drivers."}')

    def describe(self) -> dict:
        return {"mode": "claude", "model": "claude-sonnet-5"}


def main() -> int:
    from app.config.settings import get_settings
    from app.v2.commentary import judge

    settings = get_settings()

    # ---- adapter routing
    print("— judge client comes from the agents' adapter factory —")
    settings.llm_client_mode = "mock"
    check("mock mode: no judge client (advisory fallback path)",
          judge.get_judge_llm() is None)
    settings.llm_client_mode = "claude"
    settings.judge_model = ""
    llm = judge.get_judge_llm()
    check("claude mode, empty JUDGE_MODEL: same adapter, R5 default model",
          llm is not None and llm.describe()["mode"] == "claude"
          and llm.describe()["model"] == "claude-sonnet-5",
          str(llm.describe() if llm else None))
    settings.judge_model = "claude-haiku-4-5-20251001"
    llm2 = judge.get_judge_llm()
    check("JUDGE_MODEL selects the model within the active mode",
          llm2 is not None and llm2.describe()["model"] == "claude-haiku-4-5-20251001",
          str(llm2.describe() if llm2 else None))
    settings.llm_client_mode = "mock"
    settings.judge_model = ""

    # ---- honest unavailable state
    print("\n— unavailable state: sentinel scores, never 0.00 —")
    r = judge.judge_commentary(REVENUE_OUTPUT, COMMENTARY, None)
    check("no judge: scores are the UNAVAILABLE sentinel (-1.0), not 0.00",
          r["faithfulness_score"] == judge.SCORE_UNAVAILABLE
          and r["completeness_score"] == judge.SCORE_UNAVAILABLE
          and r["clarity_score"] == judge.SCORE_UNAVAILABLE, str(r))
    check("no judge: reasoning says 'Judge unavailable — human review recommended'",
          "Judge unavailable" in r["reasoning"]
          and "human review recommended" in r["reasoning"], r["reasoning"])
    r404 = judge.judge_commentary(REVENUE_OUTPUT, COMMENTARY, Erroring404LLM())
    check("model 404 (the client-env failure): UNAVAILABLE sentinel, not 0.00",
          r404["faithfulness_score"] == judge.SCORE_UNAVAILABLE
          and "not found" in r404["reasoning"], str(r404)[:120])
    check("unavailable verdict is advisory REVIEW (never FAIL, never PASS)",
          r404["verdict"] == "REVIEW", r404["verdict"])

    # ---- real score still renders as a number
    print("\n— a working judge still yields a real score —")
    rgood = judge.judge_commentary(REVENUE_OUTPUT, COMMENTARY, GoodJudgeLLM())
    check("working judge: real faithfulness score (0.90), PASS verdict",
          rgood["faithfulness_score"] == 0.9 and rgood["verdict"] == "PASS",
          str(rgood)[:100])

    # ---- publication never gated by the judge
    print("\n— judge is advisory only: publication gate is the guardrail alone —")
    import inspect

    from app.v2.commentary import generation_workflow as wf
    src = inspect.getsource(wf._run)
    gate_lines = [ln for ln in src.splitlines() if "status =" in ln and "BLOCKED" in ln]
    check("workflow status is derived from guardrail validation only "
          "(no judge/evaluation term in the gate)",
          bool(gate_lines) and all("judge" not in ln.lower() and "evaluation" not in ln.lower()
                                   for ln in gate_lines), str(gate_lines))

    print(f"\n{'=' * 60}\n{PASS} passed, {FAIL} failed"
          f"{' — OVERALL PASS' if FAIL == 0 else ''}")
    for f in FAILURES:
        print(" -", f)
    print("\nNOTE: fixture verification with stubs/config objects — the live judge "
          "on the client's working model is an OPERATOR check "
          "(docs/ROUND9_ACCEPTANCE.md).")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
