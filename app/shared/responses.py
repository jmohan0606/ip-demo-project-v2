from typing import Any
from app.models.shared import ApiEnvelope

def ok(data: Any | None = None, message: str | None = None, warnings: list[str] | None = None) -> ApiEnvelope:
    return ApiEnvelope(success=True, data=data, message=message, warnings=warnings or [])

def fail(message: str, warnings: list[str] | None = None, data: Any | None = None) -> ApiEnvelope:
    return ApiEnvelope(success=False, data=data, message=message, warnings=warnings or [])
