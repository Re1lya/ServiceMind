from fastapi import APIRouter, Request

from app.schemas.common import BaseResponse, HealthStatusData
from app.services.monitoring_service import build_health_status

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> BaseResponse[HealthStatusData]:
    """Return a lightweight dependency-aware health snapshot."""
    trace_id = getattr(request.state, "trace_id", None)
    return BaseResponse(data=await build_health_status(trace_id=trace_id))
