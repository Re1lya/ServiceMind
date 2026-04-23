from fastapi import APIRouter

router = APIRouter()


@router.get("/{session_id}")
async def get_session_detail(session_id: str) -> dict[str, str]:
    """Placeholder session endpoint."""
    return {"session_id": session_id, "message": "TODO: implement session query"}


# TODO: support session history, pagination, transcript export, and feedback records.
