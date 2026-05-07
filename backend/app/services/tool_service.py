"""Tool service module."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.exceptions import ExternalServiceException
from app.repositories.tool_log_repository import ToolLogRepository
from app.schemas.tool import (
    LogisticsQueryResultData,
    OrderQueryResultData,
    ToolInvocationResponseData,
    ToolLogItemData,
    ToolLogListResponseData,
    ToolLogPaginationData,
)
from app.tools.base import ToolExecutionResult
from app.tools.tool_registry import get_tool


class ToolService:
    """Dispatch business tools and persist invocation logs."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.tool_log_repository = ToolLogRepository(db)

    def execute_order_query(
        self,
        *,
        query: str,
        order_no: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
    ) -> ToolInvocationResponseData:
        """Run the order query tool and save an auditable invocation log."""
        result, log = self._invoke_tool(
            "order_query",
            tool_input={
                "query": query,
                "order_no": order_no,
                "user_id": user_id,
            },
            trace_id=trace_id,
            session_id=session_id,
            query=query,
            order_no=order_no,
            user_id=user_id,
        )

        result_payload = result.data or None
        return ToolInvocationResponseData(
            log_id=log.log_id,
            tool_name=result.tool_name,
            status=result.status,
            message=result.message,
            trace_id=trace_id,
            session_id=session_id,
            result=OrderQueryResultData(**result_payload) if result_payload else None,
            created_at=log.created_at,
        )

    def execute_logistics_query(
        self,
        *,
        query: str,
        order_no: str | None = None,
        tracking_no: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
    ) -> ToolInvocationResponseData:
        """Run the logistics query tool and save an auditable invocation log."""
        result, log = self._invoke_tool(
            "logistics_query",
            tool_input={
                "query": query,
                "order_no": order_no,
                "tracking_no": tracking_no,
                "user_id": user_id,
            },
            trace_id=trace_id,
            session_id=session_id,
            query=query,
            order_no=order_no,
            tracking_no=tracking_no,
            user_id=user_id,
        )

        result_payload = result.data or None
        return ToolInvocationResponseData(
            log_id=log.log_id,
            tool_name=result.tool_name,
            status=result.status,
            message=result.message,
            trace_id=trace_id,
            session_id=session_id,
            result=LogisticsQueryResultData(**result_payload) if result_payload else None,
            created_at=log.created_at,
        )

    def list_tool_logs(
        self,
        *,
        tool_name: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ToolLogListResponseData:
        """Return paginated tool invocation logs for observability and debugging."""
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size
        total = self.tool_log_repository.count(
            tool_name=tool_name,
            session_id=session_id,
            trace_id=trace_id,
            status=status,
        )
        rows = self.tool_log_repository.list_logs(
            tool_name=tool_name,
            session_id=session_id,
            trace_id=trace_id,
            status=status,
            offset=offset,
            limit=page_size,
        )
        return ToolLogListResponseData(
            pagination=ToolLogPaginationData(
                page=page,
                page_size=page_size,
                total=total,
                has_more=offset + len(rows) < total,
            ),
            items=[
                ToolLogItemData(
                    log_id=row.log_id,
                    tool_name=row.tool_name,
                    status=row.status,
                    session_id=row.session_id,
                    trace_id=row.trace_id,
                    tool_input=row.tool_input,
                    tool_output=row.tool_output,
                    error_message=row.error_message,
                    created_at=row.created_at,
                )
                for row in rows
            ],
        )

    def _invoke_tool(
        self,
        tool_name: str,
        *,
        tool_input: dict[str, object | None],
        trace_id: str | None,
        session_id: str | None,
        **kwargs,
    ):
        """Execute a registered tool, persist the outcome, and normalize unexpected failures."""
        try:
            tool = get_tool(tool_name)
            result: ToolExecutionResult = tool(**kwargs)
        except Exception as exc:
            self.tool_log_repository.create(
                tool_name=tool_name,
                status="failed",
                tool_input=json.dumps(tool_input, ensure_ascii=False),
                tool_output=None,
                error_message=str(exc),
                trace_id=trace_id,
                session_id=session_id,
            )
            raise ExternalServiceException(
                message=f"{tool_name} invocation failed",
                detail={"tool_name": tool_name},
            ) from exc

        result_payload = result.data or None
        log = self.tool_log_repository.create(
            tool_name=result.tool_name,
            status=result.status,
            tool_input=json.dumps(tool_input, ensure_ascii=False),
            tool_output=json.dumps(result_payload, ensure_ascii=False) if result_payload else None,
            error_message=None if result.status != "not_found" else result.message,
            trace_id=trace_id,
            session_id=session_id,
        )
        return result, log
