from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LlmMessage:
    role: str
    content: str


@dataclass
class LlmResponse:
    status: str
    mode: str
    content: str
    structured: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "content": self.content,
            "structured": self.structured,
            "usage": self.usage,
            "trace": self.trace,
        }
