from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """Shared API response schema."""

    code: int = 0
    message: str = "success"
    data: T | None = None


class ErrorDetail(BaseModel):
    """Structured error details for debugging and client handling."""

    trace_id: str | None = None
    detail: Any | None = None


class HealthStatusData(BaseModel):
    """Health endpoint response payload."""

    app_name: str
    app_env: str
    status: str = "ok"
    trace_id: str | None = None
    components: dict[str, str] = Field(default_factory=dict)


# TODO: add standard pagination and error response schemas.
