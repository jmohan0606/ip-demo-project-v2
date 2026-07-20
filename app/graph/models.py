from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphRuntimeResult:
    status: str
    mode: str
    operation: str
    data: Any
    fallback_used: bool = False
    message: str = ""
    tool_trace: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "operation": self.operation,
            "data": self.data,
            "fallback_used": self.fallback_used,
            "message": self.message,
            "tool_trace": self.tool_trace,
        }
