"""Per-role LLM configuration + auto-fallback (FIX_SPEC_R12).

Three LLM roles — the commentary WRITER, the JUDGE (advisory only, R9 E) and
the ASSISTANT ("Ask iPerform", R7) — may each need a different model in the
client environment. Azure/cdao route by DEPLOYMENT NAME, the model id is passed
in the request, and some models need their own api_version; the three can all
differ (a bare JUDGE_MODEL=gpt-4o-mini 404'd because it could not carry a
different api_version). Each role therefore gets an optional
(client-mode, model, deployment, api_version) tuple in .env.

This module is the ONE place role → effective-config resolution lives
(FIX_SPEC_R12 A: "do not copy-paste three times"):

    resolve_role_config("writer" | "judge" | "assistant") -> RoleLLMConfig

Key reuse (A): the assistant's client-mode key is the EXISTING
ASSISTANT_LLM_MODE (R7) and the judge keeps its EXISTING JUDGE_MODEL (R9 E);
only the genuinely new fields have new keys.

Resolution rules (identical for every role):
- every field empty  → today's behaviour: active LLM_CLIENT_MODE, the mode's
  default model (the judge keeps its R5 claude-mode different-model default).
- any field set      → the role runs on its own values, falling back PER FIELD
  to the active mode's value for anything left empty.
- deployment vs model: Azure/cdao route by deployment; if only one of the two
  is set it is used for both, best-effort, and a log line says which.

Auto-fallback (C) lives here too: build_role_llm() wraps a configured role's
client so a construction or first-call failure (bad deployment, missing
api_version, 404/400) logs a WARNING naming the role and retries ONCE with the
active default agent LLM. The served path is recorded per role:
role_config / fallback_agent_llm / unavailable. Total failure surfaces the
role-appropriate honest state at the caller (judge → UNAVAILABLE sentinel,
writer → deterministic template, assistant → honest decline) — never a
fabricated answer, and publication gating is untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.config.settings import get_settings
from app.shared.logging import get_logger

_log = get_logger("app.llm.roles")

ROLES = ("writer", "judge", "assistant")

# role -> Settings attribute per field. The assistant's mode key is the existing
# ASSISTANT_LLM_MODE; the judge's model key is the existing JUDGE_MODEL (A).
_ROLE_SETTING_ATTRS = {
    "writer": {"mode": "writer_client_mode", "model": "writer_model",
               "deployment": "writer_deployment", "api_version": "writer_api_version"},
    "judge": {"mode": "judge_client_mode", "model": "judge_model",
              "deployment": "judge_deployment", "api_version": "judge_api_version"},
    "assistant": {"mode": "assistant_llm_mode", "model": "assistant_model",
                  "deployment": "assistant_deployment", "api_version": "assistant_api_version"},
}

# The .env alias for each (role, field) — used in Env Health / operator messages.
ROLE_ENV_KEYS = {
    "writer": {"mode": "WRITER_CLIENT_MODE", "model": "WRITER_MODEL",
               "deployment": "WRITER_DEPLOYMENT", "api_version": "WRITER_API_VERSION"},
    "judge": {"mode": "JUDGE_CLIENT_MODE", "model": "JUDGE_MODEL",
              "deployment": "JUDGE_DEPLOYMENT", "api_version": "JUDGE_API_VERSION"},
    "assistant": {"mode": "ASSISTANT_LLM_MODE", "model": "ASSISTANT_MODEL",
                  "deployment": "ASSISTANT_DEPLOYMENT", "api_version": "ASSISTANT_API_VERSION"},
}


@dataclass(frozen=True)
class RoleLLMConfig:
    """A role's EFFECTIVE LLM config after per-field resolution.

    `model` / `deployment` / `api_version` are None when the role left the
    field empty (= the active mode's own default applies at construction);
    `configured_fields` lists which fields the operator explicitly set.
    """

    role: str
    mode: str
    model: str | None
    deployment: str | None
    api_version: str | None
    configured_fields: tuple[str, ...] = field(default=())

    @property
    def configured(self) -> bool:
        """True when the operator set ANY of this role's keys — only then does
        the role get its own client (+ R12 auto-fallback); all-empty keeps the
        exact pre-R12 construction path (no regression)."""
        return bool(self.configured_fields)

    def default_model_label(self) -> str:
        """What this role runs on when its model/deployment fields are empty —
        display label for Env Health / fallback messages (no secrets)."""
        return default_model_for(self.role, self.mode)


def _raw(settings, role: str, fieldname: str) -> str:
    return (getattr(settings, _ROLE_SETTING_ATTRS[role][fieldname], "") or "").strip()


def resolve_role_config(role: str, settings=None) -> RoleLLMConfig:
    """role → effective {mode, model, deployment, api_version} (FIX_SPEC_R12 A).

    The single shared resolution helper for all three roles. Empty fields
    resolve per-field to the active mode's own defaults (returned as None —
    the adapter constructors apply their existing defaults, so all-empty is
    byte-identical to pre-R12 behaviour).
    """
    if role not in ROLES:
        raise ValueError(f"unknown LLM role {role!r} (expected one of {ROLES})")
    settings = settings or get_settings()
    raw = {f: _raw(settings, role, f) for f in ("mode", "model", "deployment", "api_version")}

    # JUDGE_MODEL predates R12 (R9 E) and participated in the old behaviour:
    # it alone does NOT make the judge "configured" for R12 purposes unless a
    # NEW judge key is also set — R9 treated it as a model override within the
    # active mode, and that behaviour must not change (no regression).
    configured_fields = tuple(f for f, v in raw.items() if v)
    if role == "judge" and configured_fields == ("model",):
        configured_fields = ()
    # Likewise ASSISTANT_LLM_MODE predates R12 (R7): alone it keeps the R7
    # chain behaviour; it counts as R12 config only alongside a new key.
    if role == "assistant" and configured_fields == ("mode",):
        configured_fields = ()

    mode = (raw["mode"] or settings.llm_client_mode or "mock").lower()
    model, deployment = raw["model"] or None, raw["deployment"] or None
    if mode in ("cdao_openai", "real", "azure") and (bool(model) != bool(deployment)) and (model or deployment):
        # Azure/cdao route by deployment; only one of the pair set → best-effort
        # use it for both, and say which (FIX_SPEC_R12 A).
        which = "model" if model else "deployment"
        _log.info("role %s: only %s_%s set — using %r for both the deployment "
                  "route and the request model id (best-effort)",
                  role, role.upper(), which.upper(), model or deployment)
    return RoleLLMConfig(
        role=role, mode=mode, model=model, deployment=deployment,
        api_version=raw["api_version"] or None,
        configured_fields=configured_fields,
    )


def default_model_for(role: str, mode: str, settings=None) -> str:
    """The model a role runs on in `mode` with no explicit override — a display
    label (Env Health, fallback messages), not a constructor argument."""
    settings = settings or get_settings()
    mode = (mode or "").lower()
    if mode == "claude" and role == "judge":
        return "claude-sonnet-5"  # R5: a different model than the writer
    return {
        "mock": "deterministic-template",
        "claude": settings.anthropic_model,
        "real": settings.azure_openai_deployment,
        "cdao_openai": settings.cdao_model,
        "azure": f"SmartSDK:{settings.azure_deployment_name} (fixed at construction)",
    }.get(mode, f"unknown mode '{mode}'")


def default_api_version_for(mode: str, settings=None) -> str | None:
    """The api_version the mode's adapter uses when a role sets none."""
    settings = settings or get_settings()
    return {
        "real": settings.azure_openai_api_version,
        "cdao_openai": settings.cdao_api_version,
        "azure": settings.azure_api_version,
    }.get((mode or "").lower())


# --- C — role client construction with single-retry auto-fallback -----------

SERVED_ROLE_CONFIG = "role_config"
SERVED_FALLBACK = "fallback_agent_llm"
SERVED_UNAVAILABLE = "unavailable"


def build_configured_role_client(cfg: RoleLLMConfig):
    """Construct a role's OWN client from its resolved config, through the
    shared multi-mode builder (B). Raises on failure — callers wrap with
    RoleLLM for the R12 auto-fallback."""
    from app.llm.client import build_llm_client

    return build_llm_client(
        cfg.mode,
        model_override=cfg.model,
        deployment_override=cfg.deployment,
        api_version_override=cfg.api_version,
    )


class RoleLLM:
    """LLMClient wrapper adding the R12 auto-fallback for a CONFIGURED role.

    generate() tries the role's own client; on the first failure (construction
    already failed, or the first call 404s/400s) it logs a WARNING naming the
    role and reason and retries ONCE with the active default agent LLM
    (build_llm_client(LLM_CLIENT_MODE) — the role's keys treated as empty).
    `served_path` records which path answered: role_config /
    fallback_agent_llm / unavailable. If both fail, generate() raises so the
    caller's existing honest state engages (judge UNAVAILABLE, writer
    deterministic template, assistant decline) — nothing is fabricated.
    """

    def __init__(self, cfg: RoleLLMConfig) -> None:
        self.cfg = cfg
        self.served_path = SERVED_ROLE_CONFIG
        self._active = None
        self._fallback_tried = False
        try:
            self._active = build_configured_role_client(cfg)
        except Exception as exc:  # noqa: BLE001 — fall back once, loudly
            self._fall_back(f"construction failed: {exc}")

    def _default_client(self):
        from app.llm.client import build_llm_client

        return build_llm_client(get_settings().llm_client_mode)

    def _fall_back(self, reason: str) -> None:
        """One retry with the active default agent LLM — logged, never silent."""
        self._fallback_tried = True
        settings = get_settings()
        _log.warning(
            "role %s: configured LLM (%s model=%s deployment=%s api_version=%s) "
            "unusable — %s; falling back ONCE to the default agent LLM "
            "(LLM_CLIENT_MODE=%s)",
            self.cfg.role, self.cfg.mode, self.cfg.model, self.cfg.deployment,
            self.cfg.api_version, reason, settings.llm_client_mode)
        try:
            self._active = self._default_client()
            self.served_path = SERVED_FALLBACK
        except Exception as exc:  # noqa: BLE001 — honest unavailable state
            _log.warning("role %s: default agent LLM also unavailable: %s",
                         self.cfg.role, exc)
            self._active = None
            self.served_path = SERVED_UNAVAILABLE

    @property
    def available(self) -> bool:
        return self._active is not None

    def generate(self, prompt: str, context: dict | None = None) -> str:
        if self._active is None:
            raise RuntimeError(
                f"role {self.cfg.role}: no LLM available (configured client and "
                f"default agent LLM both failed)")
        try:
            return self._active.generate(prompt, context)
        except Exception as exc:  # noqa: BLE001 — first-call failure → one retry
            if self._fallback_tried:
                raise  # already on the default agent LLM — honest failure
            self._fall_back(f"first call failed: {exc}")
            if self._active is None:
                raise
            return self._active.generate(prompt, context)

    def describe(self) -> dict:
        inner = self._active.describe() if self._active is not None else {}
        return {**inner, "role": self.cfg.role, "served_path": self.served_path}


def build_role_llm(role: str, settings=None):
    """The role's client, or None when the role has no R12 config (callers keep
    their exact pre-R12 construction path — no regression)."""
    cfg = resolve_role_config(role, settings)
    if not cfg.configured:
        return None
    return RoleLLM(cfg)
