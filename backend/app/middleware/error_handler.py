"""Global exception middleware module."""

from __future__ import annotations

from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import BusinessException


def _trace_id_from_request(request: Request) -> str | None:
    return getattr(request.state, "trace_id", None)


def _error_payload(
    *,
    code: int,
    message: str,
    trace_id: str | None,
    detail: object | None = None,
) -> dict[str, object | None]:
    return {
        "code": code,
        "message": message,
        "data": {
            "trace_id": trace_id,
            "detail": detail,
        },
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers with standardized responses."""

    @app.exception_handler(BusinessException)
    async def handle_business_exception(request: Request, exc: BusinessException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                code=exc.code,
                message=exc.message,
                trace_id=_trace_id_from_request(request),
                detail=exc.detail,
            ),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                code=exc.status_code,
                message=str(exc.detail),
                trace_id=_trace_id_from_request(request),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                code=422,
                message="request validation failed",
                trace_id=_trace_id_from_request(request),
                detail=jsonable_encoder(exc.errors()),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_payload(
                code=500,
                message="internal server error",
                trace_id=_trace_id_from_request(request),
                detail=str(exc),
            ),
        )
