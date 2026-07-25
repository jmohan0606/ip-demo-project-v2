"""LLM connectivity rows for the Env Health screen (FIX_SPEC_R10 E, R12 D).

One row per configured LLM role — commentary writer, judge, assistant —
showing the EFFECTIVE config that role will use (mode, model, deployment,
api_version — resolved by the shared R12 helper app/llm/roles) and a live
reachability result for THAT specific configuration, from the CHEAPEST
possible check: a models-list / model-retrieve lookup on the adapter's own SDK
client, never a real generation. The judge row specifically surfaces "model
not found in subscription" (the gpt-4o-mini 404 seen in the client env) so a
bad role config shows red here BEFORE a commentary run.

R12 D — when a role's own config is unreachable, the row also says
"configured model unreachable → will fall back to <default agent model>", so
the operator sees the true state of all three roles before running anything.

Read-only diagnostic: constructs clients through the SAME guarded adapters
the agents use (app/llm/client.build_llm_client), mutates nothing, generates
nothing, and never prints secrets — mode, model/deployment name and
api_version only.

Statuses:
    model-found   the specific model was confirmed via the models endpoint
    reachable     the adapter is usable but exposes no cheap model lookup
                  (mock; SmartSDK gateway) — noted in `check`
    unavailable   the client cannot be constructed or the model lookup failed;
                  `error` carries the sanitised reason and `fallback` says
                  what the role will actually run on (R12 auto-fallback)
"""
from __future__ import annotations

from typing import Any

from app.config.settings import get_settings
from app.llm.roles import (
    ROLE_ENV_KEYS,
    RoleLLMConfig,
    default_api_version_for,
    default_model_for,
    resolve_role_config,
)

MODEL_NOT_FOUND = "model not found in subscription"


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


def _cheap_check(cfg: RoleLLMConfig) -> dict[str, Any]:
    """Constructs the role's EFFECTIVE adapter (no generation) and does the
    cheapest lookup its SDK offers. Returns {status, check, error}."""
    if cfg.mode == "mock":
        return {"status": "reachable", "error": None,
                "check": "mock adapter — local and deterministic, no external call"}
    try:
        from app.llm.client import build_llm_client
        client = build_llm_client(cfg.mode, model_override=cfg.model,
                                  deployment_override=cfg.deployment,
                                  api_version_override=cfg.api_version)
    except Exception as exc:  # noqa: BLE001 — the row must show the real reason
        return {"status": "unavailable", "check": "client construction",
                "error": _sanitize(exc)}

    inner = getattr(client, "_client", None)
    models_api = getattr(inner, "models", None)
    # The name the request routes by: deployment on the Azure-shaped adapters
    # (RealLLMClient.deployment / CdaoOpenAILLMClient.model), model elsewhere.
    resolved = getattr(client, "deployment", None) or getattr(client, "model", cfg.model)
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


def _role_row(role: str, label: str, settings) -> dict[str, Any]:
    """One role's row: effective config + reachability of THAT config (R12 D)."""
    cfg = resolve_role_config(role, settings)
    keys = ROLE_ENV_KEYS[role]
    default_mode = (settings.llm_client_mode or "mock").lower()

    # Azure/cdao route by deployment; when only the deployment is set it is
    # used for both (best-effort, per FIX_SPEC_R12 A) — show that truthfully
    # instead of the mode's default model id, which would not be requested.
    if cfg.deployment and not cfg.model and cfg.mode in ("real", "cdao_openai"):
        effective_model = cfg.deployment
    else:
        effective_model = cfg.model or default_model_for(role, cfg.mode, settings)
    effective_api_version = cfg.api_version or default_api_version_for(cfg.mode, settings)
    source = (", ".join(keys[f] for f in cfg.configured_fields)
              if cfg.configured else f"inherited from LLM_CLIENT_MODE"
              + (f" + {keys['model']}" if role == "judge" and (settings.judge_model or "").strip()
                 else ""))

    row: dict[str, Any] = {
        "role": label, "provider": cfg.mode,
        "model": effective_model,
        "deployment": cfg.deployment or ("same as model" if cfg.mode in ("real", "cdao_openai") else "—"),
        "api_version": effective_api_version or "—",
        "source": source,
    }

    # The judge never runs on the mock adapter (deterministic output cannot
    # judge language) — honest by-design row, does not redden the card.
    if role == "judge" and cfg.mode == "mock":
        row.update({"model": "—", "status": "unavailable", "check": "not constructed",
                    "error": "the judge does not run in mock mode — evaluations "
                             "record the honest UNAVAILABLE state (R9 E)"})
        return row

    row.update(_cheap_check(cfg))

    # R12 D — a configured-but-unreachable role auto-falls back at run time;
    # say so, naming what it falls back TO (mode/model only, no secrets).
    if row["status"] == "unavailable" and cfg.configured:
        fallback_model = default_model_for(role, default_mode, settings)
        row["fallback"] = (f"configured model unreachable → will fall back to the "
                           f"default agent LLM ({default_mode}: {fallback_model})")
        if role == "judge" and default_mode == "mock":
            row["fallback"] = ("configured model unreachable and the default agent "
                               "LLM is mock — the judge records the honest "
                               "UNAVAILABLE state (never 0.00, never blocks publication)")
    return row


def llm_connectivity_report() -> list[dict[str, Any]]:
    """The three role rows. Never raises; never generates; never mutates."""
    settings = get_settings()
    rows = [_role_row("writer", "commentary writer", settings),
            _role_row("judge", "judge", settings),
            _role_row("assistant", "assistant", settings)]
    # The assistant additionally has its R7 sequential chain after the primary.
    fallback_modes = (settings.assistant_llm_fallback_modes or "").strip()
    rows[2]["source"] += " (R7 chain" + (f": {fallback_modes}" if fallback_modes else "") + \
        " runs after the primary)"
    return rows
