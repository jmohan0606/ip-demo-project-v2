from __future__ import annotations

from app.llm.azure_openai_adapter import AzureOpenAiAdapter
from app.llm.mock_llm_adapter import MockLlmAdapter
from app.llm.models import LlmResponse


class LlmRuntime:
    def __init__(self) -> None:
        self.azure = AzureOpenAiAdapter()
        self.mock = MockLlmAdapter()

    def status(self) -> dict:
        return {
            "strategy": "azure_openai_first",
            "azure_openai_available": self.azure.is_available(),
            "mock_available": self.mock.is_available(),
            "active_mode": "azure_openai" if self.azure.is_available() else "mock_llm",
        }

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> LlmResponse:
        try:
            if self.azure.is_available():
                return self.azure.chat(messages, temperature)
        except Exception as exc:
            fallback = self.mock.chat(messages, temperature)
            fallback.trace.insert(0, {"mode": "azure_openai", "status": "failed", "message": str(exc)})
            return fallback
        return self.mock.chat(messages, temperature)


_llm_runtime: LlmRuntime | None = None


def get_llm_runtime() -> LlmRuntime:
    global _llm_runtime
    if _llm_runtime is None:
        _llm_runtime = LlmRuntime()
    return _llm_runtime
