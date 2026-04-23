from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def create_chat_completion() -> dict[str, str]:
    """Placeholder chat endpoint."""
    return {"message": "TODO: implement chat orchestration"}


# TODO: connect agent orchestrator, memory, tool calling, and streaming output.
