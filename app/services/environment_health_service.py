from __future__ import annotations

import time
from typing import Any

from app.config.settings import get_settings


def _check(name: str, fn) -> dict:
    """Run one probe, timing it, and normalize to {component,status,detail,error,latency_ms,...}.
    A probe returns a dict of detail fields; any exception becomes a red status with the real
    error string (never swallowed)."""
    start = time.perf_counter()
    try:
        detail = fn() or {}
        return {"component": name, "status": "green", "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                "error": None, **detail}
    except Exception as exc:  # noqa: BLE001 — the whole point is to surface the real error
        return {"component": name, "status": "red", "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                "error": f"{type(exc).__name__}: {exc}"}


class EnvironmentHealthService:
    """Active setup-verification for the client environment — the first thing opened on the client
    machine to confirm connectivity before using the app. Unlike /adapters/status (which only
    *describes* the selected adapters), this ACTIVELY exercises each one (a real generation, a real
    embedding, a real graph query, a real Chroma call) and reports green/red with the real error."""

    def report(self) -> dict:
        settings = get_settings()
        checks = [
            _check("TigerGraph", self._check_tigergraph),
            _check("LLM", self._check_llm),
        ]
        overall = "green" if all(c["status"] == "green" for c in checks) else "red"
        return {
            "overall": overall,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "modes": {
                "graph_client_mode": settings.graph_client_mode,
                "llm_client_mode": settings.llm_client_mode,
                "data_set": settings.data_set,
                "commentary_mode": settings.commentary_mode,
                "guardrail_client_mode": getattr(settings, "guardrail_client_mode", "local"),
            },
            "checks": checks,
        }

    # --- TigerGraph: reachable, auth/SSL, graph name, schema installed, per-type row counts ------
    @staticmethod
    def _check_tigergraph() -> dict[str, Any]:
        from app.graph.client import get_graph_client
        settings = get_settings()
        client = get_graph_client()
        health = client.health()
        if not health.get("healthy"):
            raise RuntimeError(health.get("error") or "graph health check failed")

        detail: dict[str, Any] = {
            "mode": health.get("mode"),
            "graph": health.get("graph") or settings.tigergraph_graph,
            "use_ssl": settings.tg_use_ssl,
            "auth": ("jwt" if settings.tg_jwt_token else "api_token" if settings.tg_api_token
                     else "secret->getToken" if settings.tg_secret else "user_pass"),
        }
        # Per-vertex-type row counts. Mock: read the loaded store; real: getVertexCount("*").
        counts: dict[str, int] = {}
        store = getattr(client, "store", None)
        if store is not None and getattr(store, "vertices", None) is not None:
            counts = {vt: len(rows) for vt, rows in store.vertices.items()}
            detail["load_report"] = health.get("load_report")
        else:
            try:  # real / tiered client with a live pyTigerGraph connection
                conn = client._pytg._connection() if hasattr(client, "_pytg") else None  # type: ignore[attr-defined]
                if conn is not None:
                    counts = {k: int(v) for k, v in conn.getVertexCount("*").items()}
            except Exception:  # noqa: BLE001 — counts are best-effort; reachability already proven
                counts = {}
        detail["schema_installed"] = len(counts) > 0
        detail["vertex_type_count"] = len(counts)
        detail["total_vertices"] = sum(counts.values())
        detail["row_counts"] = dict(sorted(counts.items(), key=lambda kv: -kv[1])[:20])
        # Honesty contract (ABSOLUTE RULE 4): if the local tier is serving while
        # GRAPH_CLIENT_MODE=real, the health screen must go RED — never report a
        # local-store answer as though it came from TigerGraph.
        served_by_tier = health.get("served_by_tier") or detail.get("served_by_tier")
        detail["served_by_tier"] = served_by_tier
        if settings.graph_client_mode == "real" and served_by_tier not in (None, 1):
            raise RuntimeError(
                f"GRAPH_CLIENT_MODE=real but requests are served by tier {served_by_tier} "
                "(local store) — TigerGraph is NOT serving"
            )
        return detail

    # --- LLM: a real test generation, latency, response shown ------------------------------------
    @staticmethod
    def _check_llm() -> dict[str, Any]:
        from app.llm.client import get_llm_client
        llm = get_llm_client()
        t0 = time.perf_counter()
        text = llm.generate(
            "Reply with the single word: OK",
            {"system_prompt": "You are a health probe. Reply concisely."},
        )
        gen_ms = round((time.perf_counter() - t0) * 1000, 1)
        if not text or not text.strip():
            raise RuntimeError("LLM returned an empty response")
        return {**llm.describe(), "generation_ms": gen_ms, "response_preview": text.strip()[:160]}
