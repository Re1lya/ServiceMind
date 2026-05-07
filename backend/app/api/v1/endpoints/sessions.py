from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.common import BaseResponse
from app.schemas.session import SessionDetailData
from app.services.session_service import get_session_detail as get_session_detail_service

router = APIRouter()


@router.get("/{session_id}")
async def get_session_detail(
    session_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> BaseResponse[SessionDetailData]:
    """Return session metadata and transcript history."""
    return BaseResponse(data=get_session_detail_service(db, session_id, page=page, page_size=page_size))


# TODO: support session history, pagination, transcript export, and feedback records.
