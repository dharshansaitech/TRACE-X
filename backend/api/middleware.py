# backend/api/middleware.py
from __future__ import annotations

import time
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Bind context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            process_time = (time.perf_counter() - start_time) * 1000  # ms

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

            logger.info(
                "http_request",
                status_code=response.status_code,
                duration_ms=round(process_time, 2),
                content_length=response.headers.get("content-length", "unknown"),
            )
            return response

        except Exception as exc:
            process_time = (time.perf_counter() - start_time) * 1000
            logger.error(
                "http_request_error",
                error=str(exc),
                duration_ms=round(process_time, 2),
                exc_info=True,
            )
            raise


class TimingMiddleware(BaseHTTPMiddleware):
    """Add X-Process-Time header to all responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        return response


class AuthHeaderMiddleware(BaseHTTPMiddleware):
    """Extract and validate auth headers, storing principal in request state."""

    SKIP_PATHS = {"/health", "/", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip auth paths
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # Store API key in request state (actual validation done in route deps)
        api_key = request.headers.get("X-API-Key") or ""
        if not api_key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]

        request.state.api_key = api_key
        return await call_next(request)
