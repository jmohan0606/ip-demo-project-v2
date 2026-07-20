from __future__ import annotations

from app.llm.models import LlmResponse


class MockLlmAdapter:
    def is_available(self) -> bool:
        return True

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> LlmResponse:
        user_text = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        concise = user_text[:500].replace("\n", " ")
        content = (
            "Answer: Based on the available context, the advisor should prioritize managed account reviews, "
            "NNM recovery, and household-level follow-up actions.\n\n"
            "Evidence used: Revenue trend, feature signals, graph context, recommendation evidence, and memory/context packet.\n\n"
            "Recommended next action: Identify the highest-opportunity households, schedule compliant review conversations, "
            "and capture accept/reject/ignore feedback to improve future recommendations.\n\n"
            "Compliance note: Use suitability-backed language and avoid promissory statements. "
            f"Prompt summary: {concise}"
        )
        return LlmResponse(
            status="success",
            mode="mock_llm",
            content=content,
            usage={"prompt_tokens": len(user_text.split()), "completion_tokens": len(content.split())},
            trace=[{"mode": "mock_llm", "status": "success", "reason": "Azure OpenAI unavailable or disabled"}],
        )
