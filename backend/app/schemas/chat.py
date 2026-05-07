from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Incoming chat request payload for the MVP closed loop."""

    session_id: str | None = Field(default=None)
    user_id: str | None = Field(default=None)
    channel: str = Field(default="web")
    stream: bool = Field(default=False)
    message: str = Field(..., min_length=1, description="User input message")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        """Reject blank messages after trimming whitespace."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank")
        return normalized


class KnowledgeSourceData(BaseModel):
    """Knowledge source surfaced to the frontend for answer traceability."""

    document_id: str
    title: str
    source_type: str
    source_path: str | None = None
    score: float
    snippet: str


class ChatResponseData(BaseModel):
    """Serialized chat completion payload returned by the MVP endpoint."""

    session_id: str
    reply: str
    route: str
    answer_source: str
    trace_id: str | None = None
    user_message_id: str
    assistant_message_id: str
    knowledge_sources: list[KnowledgeSourceData] = Field(default_factory=list)
