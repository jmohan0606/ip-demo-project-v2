"""Assistant model-provider selection (FIX_SPEC_R7 A2).

Follows the existing guarded pattern in app/llm/client.py — the SAME adapter
classes, constructed per assistant mode rather than through the app singleton,
so ASSISTANT_LLM_MODE can point the assistant at a different model than the
commentary writer without touching it.

Chain: primary = ASSISTANT_LLM_MODE (default: the app's LLM_CLIENT_MODE),
then ASSISTANT_LLM_FALLBACK_MODES in order (default per primary below —
cdao_openai is the confirmed-working client-env path; claude is the build
box). A fallback that answers is LOGGED (WARNING) and recorded on the turn's
metadata — never silent.

R12 — the PRIMARY link is built from the assistant's resolved role config
(ASSISTANT_MODEL / ASSISTANT_DEPLOYMENT / ASSISTANT_API_VERSION applied on top
of ASSISTANT_LLM_MODE, per-field); the existing sequential chain runs
UNCHANGED after it, and the R12 single-retry with the active default agent LLM
(the role's keys treated as empty) is the FINAL link after the chain, before
the honest-decline state. Each answer records the served path:
role_config (primary) / fallback_agent_llm (any later link) / unavailable.
"""
from __future__ import annotations

from app.config.settings import get_settings
from app.shared.logging import get_logger

_log = get_logger("app.v2.assistant.llm")

# Default sequential fallback per primary (A2): the client env falls from cdao
# through the SmartSDK gateway to mock (deterministic, never external); build-
# box modes fall to mock only.
_DEFAULT_FALLBACKS = {
    "cdao_openai": ["azure", "real", "mock"],
    "azure": ["cdao_openai", "real", "mock"],
    "real": ["mock"],
    "claude": ["mock"],
    "mock": [],
}


def _build(mode: str):
    from app.llm.client import (
        AzureOpenAILLMClient,
        CdaoOpenAILLMClient,
        ClaudeLLMClient,
        MockLLMClient,
        RealLLMClient,
    )

    return {
        "mock": MockLLMClient,
        "claude": ClaudeLLMClient,
        "real": RealLLMClient,
        "cdao_openai": CdaoOpenAILLMClient,
        "azure": AzureOpenAILLMClient,
    }[mode]()


class AssistantLLM:
    """generate() over the configured chain; returns text + which provider
    served + which providers failed first (surfaced in turn metadata)."""

    def __init__(self) -> None:
        settings = get_settings()
        from app.llm.roles import resolve_role_config

        self._cfg = resolve_role_config("assistant", settings)
        self._default_mode = (settings.llm_client_mode or "mock").lower()
        primary = self._cfg.mode
        override = [m.strip().lower() for m in
                    (settings.assistant_llm_fallback_modes or "").split(",") if m.strip()]
        chain = [primary] + (override or _DEFAULT_FALLBACKS.get(primary, ["mock"]))
        # de-dup, preserve order
        self.chain: list[str] = list(dict.fromkeys(chain))
        # True when any R12 ASSISTANT_* override is set (metadata surfaces the
        # served path only then, so unconfigured turns keep their R7 labels).
        self.configured: bool = self._cfg.configured
        self._clients: dict[str, object] = {}

    def describe(self) -> dict:
        return {"chain": self.chain}

    def _build_link(self, mode: str):
        """The primary link carries the assistant's R12 role config (model /
        deployment / api_version overrides); later chain links are the plain
        mode clients, exactly as R7 built them."""
        if mode == self.chain[0] and self._cfg.configured:
            from app.llm.roles import build_configured_role_client

            return build_configured_role_client(self._cfg)
        return _build(mode)

    def generate(self, prompt: str, context: dict | None = None) -> dict:
        """Returns {"text", "provider", "model", "fallback_from": [..],
        "served_path": role_config|fallback_agent_llm|unavailable} — provider
        "" and text "" when every link failed (the caller's honest-decline
        path; never a fabricated answer)."""
        failures: list[str] = []
        for mode in self.chain:
            try:
                client = self._clients.get(mode)
                if client is None:
                    client = self._clients[mode] = self._build_link(mode)
                text = client.generate(prompt, context)
                if failures:
                    _log.warning(
                        "assistant LLM FALLBACK: %s answered after %s failed",
                        mode, ", ".join(failures))
                return {
                    "text": text,
                    "provider": mode,
                    "model": str(client.describe().get("model", "")),
                    "fallback_from": list(failures),
                    "served_path": "role_config" if not failures else "fallback_agent_llm",
                }
            except Exception as exc:  # noqa: BLE001 — try the next mode, loudly
                _log.warning("assistant LLM provider %s failed: %s", mode, exc)
                failures.append(mode)

        # R12 C — FINAL link after the R7 chain is exhausted: one retry with
        # the active default agent LLM (the assistant's role keys treated as
        # empty). Skipped only when it would repeat a link already tried
        # identically (default mode in the chain with no role overrides).
        if self._cfg.configured or self._default_mode not in self.chain:
            try:
                from app.llm.client import build_llm_client

                client = build_llm_client(self._default_mode)
                text = client.generate(prompt, context)
                _log.warning(
                    "assistant LLM FALLBACK: default agent LLM (%s) answered "
                    "after chain %s failed", self._default_mode, self.chain)
                return {
                    "text": text,
                    "provider": self._default_mode,
                    "model": str(client.describe().get("model", "")),
                    "fallback_from": list(failures),
                    "served_path": "fallback_agent_llm",
                }
            except Exception as exc:  # noqa: BLE001 — honest decline next
                _log.warning("assistant LLM default agent LLM (%s) failed: %s",
                             self._default_mode, exc)
                failures.append(f"{self._default_mode} (default agent LLM)")

        _log.error("assistant LLM: every provider in chain %s failed", self.chain)
        return {"text": "", "provider": "", "model": "", "fallback_from": failures,
                "served_path": "unavailable"}
