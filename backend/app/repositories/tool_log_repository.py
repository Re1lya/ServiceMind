"""Tool log repository module."""

from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.tool_log import ToolLog
from app.utils.id_generator import generate_tool_log_id


class ToolLogRepository:
    """Encapsulate persistence operations for tool invocation logs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        tool_name: str,
        status: str,
        tool_input: str,
        tool_output: str | None = None,
        error_message: str | None = None,
        trace_id: str | None = None,
        session_id: str | None = None,
    ) -> ToolLog:
        """Create and persist a tool invocation log row."""
        log = ToolLog(
            log_id=generate_tool_log_id(),
            tool_name=tool_name,
            status=status,
            tool_input=tool_input,
            tool_output=tool_output,
            error_message=error_message,
            trace_id=trace_id,
            session_id=session_id,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def count(
        self,
        *,
        tool_name: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        status: str | None = None,
    ) -> int:
        """Return the total number of logs matching the supplied filters."""
        query = self.db.query(ToolLog)
        if tool_name:
            query = query.filter(ToolLog.tool_name == tool_name)
        if session_id:
            query = query.filter(ToolLog.session_id == session_id)
        if trace_id:
            query = query.filter(ToolLog.trace_id == trace_id)
        if status:
            query = query.filter(ToolLog.status == status)
        return query.count()

    def list_logs(
        self,
        *,
        tool_name: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[ToolLog]:
        """Return filtered logs ordered from newest to oldest."""
        query = self.db.query(ToolLog)
        if tool_name:
            query = query.filter(ToolLog.tool_name == tool_name)
        if session_id:
            query = query.filter(ToolLog.session_id == session_id)
        if trace_id:
            query = query.filter(ToolLog.trace_id == trace_id)
        if status:
            query = query.filter(ToolLog.status == status)
        return (
            query.order_by(desc(ToolLog.created_at), desc(ToolLog.id))
            .offset(offset)
            .limit(limit)
            .all()
        )
