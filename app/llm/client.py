from __future__ import annotations

import hashlib
from typing import Protocol

from app.config.settings import get_settings
from app.shared.adapter_logging import logged_adapter_call


class LLMClientError(RuntimeError):
    pass


def build_cdao_openai_client(api_version: str, workspace_id: str | None):
    """Construct the shared cdao Azure OpenAI client used by BOTH the LLM adapter
    (CdaoOpenAILLMClient) and the embedding adapter (CdaoOpenAIEmbeddingClient) — one
    construction path so the confirmed-working notebook pattern lives in exactly one place.

    GUARDED IMPORT: `cdao` exists only in the client artifactory (cdaosdk-all[openai]). It is
    imported ONLY inside this function, called ONLY when a cdao_openai mode is selected — the app
    boots normally in mock/claude/real/azure modes without it. The returned client exposes the
    standard OpenAI SDK surface (`.chat.completions.create`, `.embeddings.create`).

    PREREQUISITE (client machine): a PCL AWS login must be run BEFORE starting the app; cdao
    authenticates from that ambient AWS session, not from code/.env credentials. One login covers
    both the LLM and embedding adapters (same cdao client).
    """
    if not workspace_id:
        raise LLMClientError(
            "cdao_openai mode requires CDAO_WORKSPACE_ID in .env "
            "(plus CDAO_API_VERSION — see CLIENT_ENV_SETUP.md §1b)"
        )
    try:
        from cdao import openai_azure_client  # type: ignore  # guarded: client-only package
    except ImportError as exc:  # pragma: no cover — depends on client-only package
        raise LLMClientError(
            "cdao_openai mode requires the client-only 'cdao' package "
            "(cdaosdk-all[openai], JPMC artifactory). Install it in the client "
            "environment (uv pip install 'cdaosdk-all[openai]'), or use a build-box "
            "mode (mock|claude) here. Original error: " + str(exc)
        ) from exc
    return openai_azure_client(api_version=api_version, workspace_id=workspace_id)


def _record_llm(mode: str, model: str, prompt_text: str, out_text: str, latency_ms: float, estimated: bool = True) -> None:
    """Record an LLM call to the observability recorder (Section 11.7). Never raises."""
    try:
        from app.observability.recorder import estimate_tokens, record_llm_call
        record_llm_call(mode, model, estimate_tokens(prompt_text), estimate_tokens(out_text),
                        latency_ms, estimated=estimated)
    except Exception:  # noqa: BLE001
        pass


def _record_llm_tokens(mode: str, model: str, in_tok, out_tok, prompt_text: str, out_text: str, latency_ms: float) -> None:
    try:
        from app.observability.recorder import estimate_tokens, record_llm_call
        record_llm_call(mode, model,
                        in_tok if in_tok is not None else estimate_tokens(prompt_text),
                        out_tok if out_tok is not None else estimate_tokens(out_text),
                        latency_ms, estimated=(in_tok is None))
    except Exception:  # noqa: BLE001
        pass


class LLMClient(Protocol):
    """Adapter interface for all LLM text generation (Section 2 of the rebuild brief).

    Services build the full prompt + context themselves so that switching between
    mock/claude/real changes nothing about prompt design — only the transport.
    """

    def generate(self, prompt: str, context: dict | None = None) -> str: ...

    def describe(self) -> dict: ...


def _render_messages(prompt: str, context: dict | None) -> tuple[str, str]:
    """Shared prompt assembly used by ALL implementations, so the exact same
    system/user content reaches mock, Claude, and Azure OpenAI."""
    context = context or {}
    system_prompt = context.get(
        "system_prompt",
        "You are the iPerform Insights & Coaching assistant for a wealth management firm. "
        "Answer using only the structured context provided. Be concise, specific and "
        "compliance-aware; cite concrete figures from the context when available.",
    )
    context_lines = [
        f"- {key}: {value}"
        for key, value in context.items()
        if key != "system_prompt" and value is not None
    ]
    user_content = prompt if not context_lines else prompt + "\n\nContext:\n" + "\n".join(context_lines)
    return system_prompt, user_content


class MockLLMClient:
    """Deterministic template generator — default driver for routine iteration.

    Uses the same assembled prompt inputs as the real clients, echoing the key
    context signals so downstream pages render meaningful, stable text without
    burning tokens on every hot reload.
    """

    @logged_adapter_call("llm")
    def generate(self, prompt: str, context: dict | None = None) -> str:
        import time as _t
        _start = _t.perf_counter()
        system_prompt, user_content = _render_messages(prompt, context)
        context = context or {}
        digest = hashlib.sha256(user_content.encode("utf-8")).hexdigest()[:8]
        signal_keys = [k for k in context if k != "system_prompt"][:6]
        signals = ", ".join(f"{k}={context[k]}" for k in signal_keys) if signal_keys else "no structured signals"
        out = (
            f"[mock-llm {digest}] {prompt.strip().splitlines()[0][:160]} — "
            f"Deterministic draft based on: {signals}. "
            "Switch LLM_CLIENT_MODE=claude to spot-check real model output with identical inputs."
        )
        _record_llm("mock", "deterministic-template", user_content, out,
                    (_t.perf_counter() - _start) * 1000, estimated=True)
        return out

    def describe(self) -> dict:
        return {"mode": "mock", "model": "deterministic-template"}


class ClaudeLLMClient:
    """Anthropic-backed client for local validation of real LLM output quality.

    Default model claude-haiku-4-5-20251001 (cheapest tier) per the rebuild brief —
    do not default to a more expensive model without being asked.
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise LLMClientError("LLM_CLIENT_MODE=claude requires ANTHROPIC_API_KEY in .env")
        import anthropic  # imported here so nothing outside this class depends on the SDK

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    @logged_adapter_call("llm")
    def generate(self, prompt: str, context: dict | None = None) -> str:
        import time as _t
        _start = _t.perf_counter()
        system_prompt, user_content = _render_messages(prompt, context)
        response = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = getattr(response, "usage", None)
        _record_llm_tokens("claude", self.model,
                           getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None),
                           user_content, text, (_t.perf_counter() - _start) * 1000)
        return text

    def describe(self) -> dict:
        return {"mode": "claude", "model": self.model}


class RealLLMClient:
    """Azure OpenAI-backed client — what runs at the client site. Uses the exact
    same assembled prompts as ClaudeLLMClient so cutover is env-only."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
            raise LLMClientError(
                "LLM_CLIENT_MODE=real requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in .env"
            )
        from openai import AzureOpenAI  # imported here so nothing outside this class depends on the SDK

        self._client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self.deployment = settings.azure_openai_deployment

    @logged_adapter_call("llm")
    def generate(self, prompt: str, context: dict | None = None) -> str:
        import time as _t
        _start = _t.perf_counter()
        system_prompt, user_content = _render_messages(prompt, context)
        response = self._client.chat.completions.create(
            model=self.deployment,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        _record_llm_tokens("real", f"azure:{self.deployment}",
                           getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None),
                           user_content, text, (_t.perf_counter() - _start) * 1000)
        return text

    def describe(self) -> dict:
        return {"mode": "real", "model": f"azure:{self.deployment}"}


class AzureOpenAILLMClient:
    """Azure OpenAI via JPMC's SmartSDK / Fusion gateway — the client-site LLM path.

    Builds a `smart_sdk.models.Model` and converts it to a LangGraph-usable chat model with
    `_to_langgraph_model` (SMARTSDK_REFERENCE.md sections 1-3), then invokes it with the exact
    same assembled system/user prompt every other adapter uses — so switching mock/claude/real/
    azure changes only the transport, never prompt design.

    `smart_sdk` lives only in the client artifactory, so its import is GUARDED: it is imported
    ONLY here, inside __init__, and only when LLM_CLIENT_MODE=azure. The app boots normally in
    mock/claude/real mode on a machine without smart_sdk installed.

    Two auth methods (SMARTSDK_REFERENCE.md 1 & 2), selected by AZURE_AUTH_METHOD:
      key         → Model(api_key, azure_*, fusion_base_url/workspace_id/env)   [primary]
      certificate → Model(auth_method=CERTIFICATE, certificate_path, tenant_id, client_id, ...)
    """

    def __init__(self) -> None:
        settings = get_settings()
        # Guarded import — smart_sdk is only present in the client environment.
        try:
            from smart_sdk.models import Model, ModelProvider  # type: ignore
            from smart_sdk.ext.langgraph.models._models import _to_langgraph_model  # type: ignore
        except ImportError as exc:  # pragma: no cover — depends on client-only package
            raise LLMClientError(
                "LLM_CLIENT_MODE=azure requires the client-only 'smart_sdk' package "
                "(JPMC artifactory). Install it in the client environment, or use "
                "LLM_CLIENT_MODE=mock|claude|real here. Original error: " + str(exc)
            ) from exc

        auth_method = (settings.azure_auth_method or "key").lower()
        if auth_method == "certificate":
            from smart_sdk.models import AuthMethod  # type: ignore
            if not settings.azure_certificate_path:
                raise LLMClientError("AZURE_AUTH_METHOD=certificate requires AZURE_CERTIFICATE_PATH")
            model = Model(
                name=settings.azure_model_name,
                auth_method=AuthMethod.CERTIFICATE,
                provider=ModelProvider.AZURE_OPENAI,
                azure_endpoint=settings.azure_endpoint,
                azure_api_version=settings.azure_api_version,
                azure_deployment_name=settings.azure_deployment_name,
                certificate_path=settings.azure_certificate_path,
                api_key=settings.azure_api_key,
                tenant_id=settings.azure_tenant_id,
                client_id=settings.azure_client_id,
            )
        else:  # key / fusion (primary, confirmed-working)
            if not settings.azure_api_key or not settings.fusion_base_url:
                raise LLMClientError(
                    "LLM_CLIENT_MODE=azure (key auth) requires AZURE_API_KEY and FUSION_BASE_URL "
                    "(plus FUSION_WORKSPACE_ID / FUSION_ENV) — see CLIENT_ENV_SETUP.md"
                )
            model = Model(
                name=settings.azure_model_name,
                provider=ModelProvider.AZURE_OPENAI,
                azure_deployment_name=settings.azure_deployment_name,
                api_key=settings.azure_api_key,
                azure_api_version=settings.azure_api_version,
                azure_endpoint=settings.azure_endpoint or settings.fusion_base_url,
                fusion_base_url=settings.fusion_base_url,
                fusion_workspace_id=settings.fusion_workspace_id,
                fusion_env=settings.fusion_env,
            )
        self._model = model
        self._llm = _to_langgraph_model(model)
        self.model = f"azure-smartsdk:{settings.azure_deployment_name}"
        self._auth_method = auth_method

    @staticmethod
    def _extract_text(response) -> str:
        """A LangGraph/LangChain model .invoke() returns an AIMessage-like object with
        `.content` (str, or a list of content blocks). Normalize to plain text."""
        content = getattr(response, "content", response)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    parts.append(block.get("text", ""))
                else:
                    parts.append(getattr(block, "text", ""))
            return "".join(parts)
        return str(content)

    @logged_adapter_call("llm")
    def generate(self, prompt: str, context: dict | None = None) -> str:
        import time as _t
        _start = _t.perf_counter()
        system_prompt, user_content = _render_messages(prompt, context)
        # Dict-role messages are accepted by LangChain chat models' .invoke(); this avoids a
        # hard dependency on importing specific message classes here.
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        response = self._llm.invoke(messages)
        text = self._extract_text(response)
        usage = getattr(response, "usage_metadata", None) or {}
        _record_llm_tokens("azure", self.model,
                           usage.get("input_tokens") if isinstance(usage, dict) else None,
                           usage.get("output_tokens") if isinstance(usage, dict) else None,
                           user_content, text, (_t.perf_counter() - _start) * 1000)
        return text

    def describe(self) -> dict:
        return {"mode": "azure", "model": self.model, "auth_method": self._auth_method}


class CdaoOpenAILLMClient:
    """Azure OpenAI via the client's cdao SDK — the PRIMARY client-site LLM path
    (LLM_CLIENT_MODE=cdao_openai). Confirmed working by the developer in the client's
    Jupyter environment; the SmartSDK AzureOpenAILLMClient (mode=azure) stays as the
    secondary alternate.

    Pattern (verified in the client notebook):
        from cdao import openai_azure_client
        client = openai_azure_client(api_version=..., workspace_id=...)
        client.chat.completions.create(model=..., messages=[...]).choices[0].message.content

    The cdao client is the standard OpenAI SDK shape, so generate() maps 1:1 onto the
    same messages the other adapters send (_render_messages) and returns the same plain
    string every LangGraph agent node consumes via get_llm_client().generate() — the
    agentic flow is unchanged, only the transport differs. (Inspection note: no agent
    node uses a LangChain model object / .bind_tools; they all call generate() -> str,
    so no LangChain wrapper is needed.)

    GUARDED IMPORT: `cdao` exists only in the client artifactory (cdaosdk-all[openai]).
    It is imported ONLY here, inside __init__, and only when this mode is selected —
    the app boots normally in mock/claude/real/azure modes without it.

    PREREQUISITE (client machine): a PCL AWS login must be run BEFORE starting the app;
    cdao authenticates from that ambient AWS session, not from code/.env credentials.
    """

    def __init__(self) -> None:
        settings = get_settings()
        # Construct once (shared cdao client builder); reused for every generate() call.
        self._client = build_cdao_openai_client(
            api_version=settings.cdao_api_version,
            workspace_id=settings.cdao_workspace_id,
        )
        self.model = settings.cdao_model

    @logged_adapter_call("llm")
    def generate(self, prompt: str, context: dict | None = None) -> str:
        import time as _t
        _start = _t.perf_counter()
        system_prompt, user_content = _render_messages(prompt, context)
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        _record_llm_tokens("cdao_openai", f"cdao:{self.model}",
                           getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None),
                           user_content, text, (_t.perf_counter() - _start) * 1000)
        return text

    def describe(self) -> dict:
        return {"mode": "cdao_openai", "model": f"cdao:{self.model}"}


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Select the LLMClient per LLM_CLIENT_MODE (mock | claude | real | cdao_openai | azure).

    Client site: `cdao_openai` = cdao SDK Azure client (PRIMARY, confirmed-working);
    `azure` = JPMC SmartSDK/Fusion gateway (secondary alternate). `real` = direct Azure
    OpenAI SDK; `claude`/`mock` = build-box modes.
    """
    global _llm_client
    if _llm_client is None:
        mode = get_settings().llm_client_mode.lower()
        if mode == "mock":
            _llm_client = MockLLMClient()
        elif mode == "claude":
            _llm_client = ClaudeLLMClient()
        elif mode == "real":
            _llm_client = RealLLMClient()
        elif mode == "cdao_openai":
            _llm_client = CdaoOpenAILLMClient()
        elif mode == "azure":
            _llm_client = AzureOpenAILLMClient()
        else:
            raise LLMClientError(
                f"Unknown LLM_CLIENT_MODE '{mode}' (expected mock|claude|real|cdao_openai|azure)"
            )
    return _llm_client


def reset_llm_client() -> None:
    global _llm_client
    _llm_client = None
