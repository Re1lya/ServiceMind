from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import BusinessException
from app.schemas.common import BaseResponse
from app.schemas.tool import (
    LogisticsQueryRequest,
    OrderQueryRequest,
    ToolInvocationResponseData,
    ToolLogListResponseData,
)
from app.services.tool_service import ToolService

router = APIRouter()


@router.post("/order-query")
async def query_order_tool(
    payload: OrderQueryRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> BaseResponse[ToolInvocationResponseData]:
    """Execute the MVP order query tool directly for local debugging."""
    trace_id = getattr(request.state, "trace_id", None)
    service = ToolService(db)
    return BaseResponse(
        data=service.execute_order_query(
            query=payload.query,
            order_no=payload.order_no,
            user_id=payload.user_id,
            session_id=payload.session_id,
            trace_id=trace_id,
        )
    )


@router.post("/logistics-query")
async def query_logistics_tool(
    payload: LogisticsQueryRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> BaseResponse[ToolInvocationResponseData]:
    """Execute the MVP logistics query tool directly for local debugging."""
    trace_id = getattr(request.state, "trace_id", None)
    service = ToolService(db)
    return BaseResponse(
        data=service.execute_logistics_query(
            query=payload.query,
            order_no=payload.order_no,
            tracking_no=payload.tracking_no,
            user_id=payload.user_id,
            session_id=payload.session_id,
            trace_id=trace_id,
        )
    )


@router.get("/logs")
async def list_tool_logs(
    tool_name: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> BaseResponse[ToolLogListResponseData]:
    """Return paginated tool logs for local debugging and module-level observability."""
    service = ToolService(db)
    return BaseResponse(
        data=service.list_tool_logs(
            tool_name=tool_name,
            session_id=session_id,
            trace_id=trace_id,
            status=status,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/complaint-create")
async def create_complaint_tool() -> None:
    """Reserve the route for a later complaint module."""
    raise BusinessException(message="complaint tool is not implemented in a later module yet", code=10003, status_code=501)
