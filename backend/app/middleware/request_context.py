"""Request context middleware module."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach minimal request-scoped metadata for tracing and debugging."""

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        request.state.trace_id = trace_id
        request.state.request_started_at = time.time()

        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
