"""LLM connectivity rows for the Env Health screen (FIX_SPEC_R10 E).

One row per configured LLM role — commentary writer, judge, assistant —
showing its provider/mode, its RESOLVED model, and a live reachability result
from the CHEAPEST possible check: a models-list / model-retrieve lookup on the
adapter's own SDK client, never a real generation. The judge row specifically
surfaces "model not found in subscription" (the gpt-4o-mini 404 seen in the
client env) so a bad JUDGE_MODEL shows red here BEFORE a commentary run.

Read-only diagnostic: constructs clients through the SAME guarded adapters
the agents use (app/llm/client.build_llm_client), mutates nothing, generates
nothing, and never prints secrets — provider and model name only.

Statuses:
    model-found   the specific model was confirmed via the models endpoint
    reachable     the adapter is usable but exposes no cheap model lookup
                  (mock; SmartSDK gateway) — noted in `check`
    unavailable   the client cannot be constructed or the model lookup failed;
                  `error` carries the sanitised reason
"""
from __future__ import annotations

from typing import Any

from app.config.settings import get_settings

MODEL_NOT_FOUND = "model not found in subscription"


def _resolved_model(settings, mode: str, override: str | None = None) -> str:
    """The model a role would run on, from config only (no construction)."""
    if override:
        return override
    return {
        "mock": "mock (deterministic, no external model)",
        "claude": settings.anthropic_model,
        "real": getattr(settings, "azure_openai_deployment", "") or "azure-openai default",
        "cdao_openai": settings.cdao_model,
        "azure": "SmartSDK-configured model (fixed at construction)",
    }.get(mode, f"unknown mode '{mode}'")


def _sanitize(exc: Exception) -> str:
    """Error text with any secret-looking material stripped — the message is
    the SDK's; belt-and-braces against a key echoing back."""
    text = f"{type(exc).__name__}: {exc}"
    settings = get_settings()
    for secret in (settings.anthropic_api_key, getattr(settings, "tg_api_token", None),
                   getattr(settings, "tg_jwt_token", None), getattr(settings, "tg_secret", None)):
        if secret:
            text = text.replace(str(secret), "***")
    return text[:300]


def _is_not_found(exc: Exception) -> bool:
    text = str(exc).lower()
    return "404" in text or "not found" in text or "notfound" in type(exc).__name__.lower()


def _cheap_check(mode: str, model: str) -> dict[str, Any]:
    """Constructs the adapter (no generation) and does the cheapest lookup its
    SDK offers. Returns {status, check, error}."""
    mode = (mode or "").lower()
    if mode == "mock":
        return {"status": "reachable", "error": None,
                "check": "mock adapter — local and deterministic, no external call"}
    try:
        from app.llm.client import build_llm_client
        client = build_llm_client(mode, model_override=model or None)
    except Exception as exc:  # noqa: BLE001 — the row must show the real reason
        return {"status": "unavailable", "check": "client construction",
                "error": _sanitize(exc)}

    inner = getattr(client, "_client", None)
    models_api = getattr(inner, "models", None)
    resolved = getattr(client, "model", model)
    if models_api is None:
        return {"status": "reachable", "error": None,
                "check": "client constructed; this adapter exposes no models "
                         "endpoint, so no cheap per-model lookup exists"}
    # Cheapest: retrieve the exact model; fall back to listing and searching.
    try:
        models_api.retrieve(resolved)
        return {"status": "model-found", "error": None,
                "check": f"models.retrieve({resolved!r}) — no generation"}
    except Exception as exc:  # noqa: BLE001
        if _is_not_found(exc):
            return {"status": "unavailable", "check": f"models.retrieve({resolved!r})",
                    "error": f"{MODEL_NOT_FOUND} — {_sanitize(exc)}"}
        try:
            ids = {getattr(m, "id", "") for m in models_api.list()}
            if resolved in ids:
                return {"status": "model-found", "error": None,
                        "check": "models.list() lookup — no generation"}
            return {"status": "unavailable", "check": "models.list() lookup",
                    "error": f"{MODEL_NOT_FOUND} — '{resolved}' absent from the "
                             f"{len(ids)} models this subscription lists"}
        except Exception as exc2:  # noqa: BLE001
            return {"status": "unavailable", "check": "models.retrieve + models.list",
                    "error": _sanitize(exc2)}


def llm_connectivity_report() -> list[dict[str, Any]]:
    """The three role rows. Never raises; never generates; never mutates."""
    settings = get_settings()
    app_mode = (settings.llm_client_mode or "mock").lower()

    rows: list[dict[str, Any]] = []

    # 1 — commentary writer: the app's primary LLM (LLM_CLIENT_MODE).
    writer_model = _resolved_model(settings, app_mode)
    rows.append({"role": "commentary writer", "provider": app_mode,
                 "model": writer_model, "source": "LLM_CLIENT_MODE",
                 **_cheap_check(app_mode, "" if app_mode in ("mock", "azure") else writer_model)})

    # 2 — judge: same mode, JUDGE_MODEL override (empty = mode default; claude
    # keeps the R5 different-model default). Mock mode has no judge at all.
    if app_mode == "mock":
        rows.append({"role": "judge", "provider": app_mode, "model": "—",
                     "source": "JUDGE_MODEL (within LLM_CLIENT_MODE)",
                     "status": "unavailable", "check": "not constructed",
                     "error": "the judge does not run in mock mode — evaluations "
                              "record the honest UNAVAILABLE state (R9 E)"})
    else:
        judge_model = (settings.judge_model or "").strip()
        if not judge_model and app_mode == "claude":
            judge_model = "claude-sonnet-5"
        resolved_judge = judge_model or _resolved_model(settings, app_mode)
        rows.append({"role": "judge", "provider": app_mode, "model": resolved_judge,
                     "source": "JUDGE_MODEL (within LLM_CLIENT_MODE)",
                     **_cheap_check(app_mode, judge_model or ("" if app_mode == "azure"
                                                              else resolved_judge))})

    # 3 — assistant: ASSISTANT_LLM_MODE primary (default = the app mode).
    asst_mode = (settings.assistant_llm_mode or app_mode or "mock").lower()
    asst_model = _resolved_model(settings, asst_mode)
    rows.append({"role": "assistant", "provider": asst_mode, "model": asst_model,
                 "source": "ASSISTANT_LLM_MODE (falls back per R7 A2 chain)",
                 **_cheap_check(asst_mode, "" if asst_mode in ("mock", "azure") else asst_model)})
    return rows
