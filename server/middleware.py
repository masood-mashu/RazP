"""
RazP Security Middlewares.
Provides Request Correlation ID propagation, Security Headers, and Sanitized Error Handling.
"""

import uuid
import logging
import traceback
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("razp.security")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every inbound request has an X-Correlation-ID header and sets request.state.correlation_id.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = f"corr_{uuid.uuid4().hex[:12]}"

        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies production-grade security headers to all HTTP responses.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response


class SafeExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """
    Catches uncaught exceptions, redacts internal credentials/SQL tracebacks,
    and returns a clean, structured JSON error response with the correlation ID.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            correlation_id = getattr(request.state, "correlation_id", "corr_unknown")
            logger.error(
                f"[Unhandled Exception] Correlation ID: {correlation_id} - Error: {str(exc)}\n{traceback.format_exc()}"
            )

            # Never expose internal credentials, stack traces, or raw database connection strings
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An internal error occurred while processing your request.",
                        "correlation_id": correlation_id
                    }
                },
                headers={"X-Correlation-ID": correlation_id}
            )
