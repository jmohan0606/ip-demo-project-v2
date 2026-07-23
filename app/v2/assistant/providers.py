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
        primary = (settings.assistant_llm_mode or settings.llm_client_mode or "mock").lower()
        override = [m.strip().lower() for m in
                    (settings.assistant_llm_fallback_modes or "").split(",") if m.strip()]
        chain = [primary] + (override or _DEFAULT_FALLBACKS.get(primary, ["mock"]))
        # de-dup, preserve order
        self.chain: list[str] = list(dict.fromkeys(chain))
        self._clients: dict[str, object] = {}

    def describe(self) -> dict:
        return {"chain": self.chain}

    def generate(self, prompt: str, context: dict | None = None) -> dict:
        """Returns {"text", "provider", "model", "fallback_from": [..]} —
        provider "" and text "" when every mode in the chain failed."""
        failures: list[str] = []
        for mode in self.chain:
            try:
                client = self._clients.get(mode)
                if client is None:
                    client = self._clients[mode] = _build(mode)
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
                }
            except Exception as exc:  # noqa: BLE001 — try the next mode, loudly
                _log.warning("assistant LLM provider %s failed: %s", mode, exc)
                failures.append(mode)
        _log.error("assistant LLM: every provider in chain %s failed", self.chain)
        return {"text": "", "provider": "", "model": "", "fallback_from": failures}
