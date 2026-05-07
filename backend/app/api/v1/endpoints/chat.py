from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.chat import ChatRequest, ChatResponseData
from app.schemas.common import BaseResponse
from app.services.chat_service import handle_chat_request

router = APIRouter()


@router.post("/")
async def create_chat_completion(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> BaseResponse[ChatResponseData]:
    """Create a minimal persisted chat completion for the MVP."""
    trace_id = getattr(request.state, "trace_id", None)
    return BaseResponse(data=await handle_chat_request(db, payload, trace_id=trace_id))


# TODO: connect agent orchestrator, memory, tool calling, and streaming output.
