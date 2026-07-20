from __future__ import annotations

"""Section 11.7 — observability depth: per-LLM-call token/cost + per-request stage latency.

A lightweight in-process ring buffer (no DB, resets per process — same honesty as the mock
graph store). Real token counts come from the Claude adapter's response.usage; mock calls are
estimated from text length. Surfaced on the Admin Observability tab + agent timelines.
"""

import time
from collections import deque
from threading import Lock

# Approx Claude Haiku 4.5 pricing ($/1M tokens) — for a real cost estimate, honest and labeled.
_COST_PER_MTOK = {"input": 0.80, "output": 4.0}
_MAX = 200

_llm_calls: deque = deque(maxlen=_MAX)
_stage_spans: deque = deque(maxlen=_MAX)
_lock = Lock()


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)  # ~4 chars/token heuristic


def record_llm_call(mode: str, model: str, input_tokens: int, output_tokens: int,
                    latency_ms: float, estimated: bool = False) -> None:
    cost = round(input_tokens / 1e6 * _COST_PER_MTOK["input"]
                 + output_tokens / 1e6 * _COST_PER_MTOK["output"], 6)
    with _lock:
        _llm_calls.append({
            "seq": len(_llm_calls) + 1, "mode": mode, "model": model,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "latency_ms": round(latency_ms, 1), "cost_usd": cost, "estimated": estimated,
        })


def record_stage(request_label: str, stages: list[dict]) -> None:
    """stages = [{name, ms}]. One request's stage-latency trace (the SYSTEM TRACE bar)."""
    with _lock:
        _stage_spans.append({"request": request_label, "stages": stages,
                             "total_ms": round(sum(s.get("ms", 0) for s in stages), 1)})


def llm_calls(limit: int = 50) -> list[dict]:
    with _lock:
        return list(_llm_calls)[-limit:][::-1]


def stage_spans(limit: int = 20) -> list[dict]:
    with _lock:
        return list(_stage_spans)[-limit:][::-1]


def summary() -> dict:
    with _lock:
        calls = list(_llm_calls)
    n = len(calls)
    return {
        "llm_call_count": n,
        "total_tokens": sum(c["total_tokens"] for c in calls),
        "total_cost_usd": round(sum(c["cost_usd"] for c in calls), 6),
        "avg_latency_ms": round(sum(c["latency_ms"] for c in calls) / n, 1) if n else 0.0,
        "by_mode": {m: sum(1 for c in calls if c["mode"] == m) for m in {c["mode"] for c in calls}},
        "real_calls": sum(1 for c in calls if not c["estimated"]),
        "estimated_calls": sum(1 for c in calls if c["estimated"]),
    }


class stage_timer:
    """Context manager to time a named stage and collect it into a list for record_stage."""

    def __init__(self, name: str, sink: list[dict]) -> None:
        self.name, self.sink = name, sink

    def __enter__(self):
        self._t = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.sink.append({"name": self.name, "ms": round((time.perf_counter() - self._t) * 1000, 1)})
