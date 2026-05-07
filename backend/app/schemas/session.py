from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionMessageItem(BaseModel):
    """Serialized message payload inside a session transcript."""

    model_config = ConfigDict(from_attributes=True)

    message_id: str
    role: str
    content: str
    message_type: str
    trace_id: str | None
    created_at: datetime


class PaginationMeta(BaseModel):
    """Pagination metadata for transcript slices."""

    page: int
    page_size: int
    total: int
    has_more: bool


class SessionDetailData(BaseModel):
    """Structured session detail response payload."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    user_id: str | None
    channel: str
    status: str
    created_at: datetime
    updated_at: datetime
    pagination: PaginationMeta
    messages: list[SessionMessageItem]
