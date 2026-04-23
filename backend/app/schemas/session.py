from pydantic import BaseModel


class SessionDetailResponse(BaseModel):
    """TODO: define session detail response."""

    session_id: str
    message: str
