from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """TODO: define chat request payload."""

    session_id: str | None = Field(default=None)
    message: str = Field(default="", description="User input message")


class ChatResponse(BaseModel):
    """TODO: define chat response payload."""

    reply: str = "TODO"
