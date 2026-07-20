"""Global FastAPI exception handlers.

Every handler logs with structured context (the correlation id is attached
automatically by the log formatter) and returns a clean, consistent JSON error
envelope to the client — a raw stack trace is NEVER sent to the user. Full traces
for unexpected errors go only to the logs (logs/app.log or the configured sink).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.shared.correlation import get_correlation_id
from app.shared.exceptions import ConfigurationError, IPerformError, NotFoundError, ValidationError
from app.shared.logging import get_logger

logger = get_logger("app.api")


def _error_body(message: str, error_type: str) -> dict:
    """Consistent client-facing error envelope, tagged with the correlation id so a
    user/support can quote it and we can find the matching server-side trace."""
    return {
        "success": False,
        "error": error_type,
        "message": message,
        "correlation_id": get_correlation_id(),
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(request: Request, exc: ConfigurationError):
        logger.warning("Configuration error at %s: %s", request.url.path, exc)
        return JSONResponse(status_code=400, content=_error_body(str(exc), "configuration_error"))

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        logger.warning("Validation error at %s: %s", request.url.path, exc)
        return JSONResponse(status_code=422, content=_error_body(str(exc), "validation_error"))

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(request: Request, exc: NotFoundError):
        logger.warning("Not found at %s: %s", request.url.path, exc)
        return JSONResponse(status_code=404, content=_error_body(str(exc), "not_found"))

    @app.exception_handler(IPerformError)
    async def iperform_error_handler(request: Request, exc: IPerformError):
        logger.warning("Application error at %s: %s", request.url.path, exc)
        return JSONResponse(status_code=400, content=_error_body(str(exc), "application_error"))

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        # Full trace to logs only; the client gets a clean, generic message plus the
        # correlation id to quote when reporting the failure.
        logger.error(
            "Unhandled error at %s: %s",
            request.url.path,
            exc,
            exc_info=True,
            extra={"path": request.url.path, "method": request.method, "error_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=500,
            content=_error_body("Unexpected server error", "internal_error"),
        )
