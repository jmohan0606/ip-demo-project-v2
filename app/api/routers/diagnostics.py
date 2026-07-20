"""Diagnostics routes — deliberate error hooks for verifying logging/observability.

Registered only when ``ENABLE_DIAGNOSTICS_ROUTES`` is true (default; kept out of
production). These let an operator confirm that an unhandled error lands in the log
sink with a full stack trace and correlation id, while the client still receives a
clean structured error — the exact end-to-end check for CloudWatch wiring.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.shared.exceptions import ValidationError
from app.shared.logging import get_logger

router = APIRouter(prefix="/_diagnostics", tags=["diagnostics"])
_log = get_logger("app.diagnostics")


@router.get("/ping")
def ping() -> dict:
    """Emit an INFO log line and return OK — confirms the sink is receiving records."""
    _log.info("diagnostics ping")
    return {"status": "ok"}


@router.get("/boom")
def boom() -> dict:
    """Raise an unhandled error on purpose. The global exception handler logs the
    full trace (with correlation id) and returns a clean 500 body to the caller."""
    raise RuntimeError("Deliberate diagnostics error to verify structured logging")


@router.get("/handled-error")
def handled_error() -> dict:
    """Raise a domain error to verify the typed-handler path (clean 422 + trace-free
    body, warning-level log)."""
    raise ValidationError("Deliberate handled validation error")
