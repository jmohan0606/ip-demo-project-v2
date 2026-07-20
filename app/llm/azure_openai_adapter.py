from __future__ import annotations

from typing import Any

from app.config import get_runtime_config
from app.llm.models import LlmResponse


class AzureOpenAiAdapter:
    def __init__(self) -> None:
        self.config = get_runtime_config()
        self.client: Any | None = None
        self.error: str | None = None
        self._initialize()

    def _initialize(self) -> None:
        if not self.config.azure_openai_enabled:
            return
        try:
            from openai import AzureOpenAI  # type: ignore
            self.client = AzureOpenAI(
                api_key=self.config.azure_openai_api_key,
                azure_endpoint=self.config.azure_openai_endpoint,
                api_version=self.config.azure_openai_api_version,
            )
        except Exception as exc:  # pragma: no cover - optional dependency/env
            self.error = str(exc)

    def is_available(self) -> bool:
        return bool(self.config.azure_openai_enabled and self.client and self.config.azure_openai_deployment)

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> LlmResponse:
        if not self.is_available():
            raise RuntimeError(self.error or "Azure OpenAI is not available")
        response = self.client.chat.completions.create(
            model=self.config.azure_openai_deployment,
            messages=messages,
            temperature=temperature,
        )
        content = response.choices[0].message.content or ""
        usage = {}
        if getattr(response, "usage", None):
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
                "completion_tokens": getattr(response.usage, "completion_tokens", None),
                "total_tokens": getattr(response.usage, "total_tokens", None),
            }
        return LlmResponse(
            status="success",
            mode="azure_openai",
            content=content,
            usage=usage,
            trace=[{"mode": "azure_openai", "status": "success"}],
        )
