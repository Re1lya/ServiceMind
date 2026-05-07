from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class OrderQueryRequest(BaseModel):
    """Direct tool request payload for order lookup."""

    query: str = Field(..., min_length=1)
    order_no: str | None = None
    user_id: str | None = None
    session_id: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized


class LogisticsQueryRequest(BaseModel):
    """Direct tool request payload for logistics lookup."""

    query: str = Field(..., min_length=1)
    order_no: str | None = None
    tracking_no: str | None = None
    user_id: str | None = None
    session_id: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized


class OrderQueryResultData(BaseModel):
    """Structured order detail returned by the MVP order tool."""

    order_no: str
    status: str
    amount: float
    currency: str
    item_count: int
    created_at: str
    estimated_delivery_at: str
    summary: str


class LogisticsQueryResultData(BaseModel):
    """Structured logistics detail returned by the MVP logistics tool."""

    order_no: str
    tracking_no: str
    carrier: str
    status: str
    estimated_delivery_at: str
    current_node: str
    timeline: list[str]


class ToolInvocationResponseData(BaseModel):
    """Standardized tool invocation response payload."""

    log_id: str
    tool_name: str
    status: str
    message: str
    trace_id: str | None = None
    session_id: str | None = None
    result: OrderQueryResultData | LogisticsQueryResultData | None = None
    created_at: datetime


class ToolLogItemData(BaseModel):
    """Serialized tool invocation log row."""

    log_id: str
    tool_name: str
    status: str
    session_id: str | None = None
    trace_id: str | None = None
    tool_input: str
    tool_output: str | None = None
    error_message: str | None = None
    created_at: datetime


class ToolLogPaginationData(BaseModel):
    """Pagination metadata for tool log listings."""

    page: int
    page_size: int
    total: int
    has_more: bool


class ToolLogListResponseData(BaseModel):
    """Tool log list response payload."""

    pagination: ToolLogPaginationData
    items: list[ToolLogItemData]
