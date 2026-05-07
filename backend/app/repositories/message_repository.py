"""Message repository module."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.message import Message
from app.utils.id_generator import generate_message_id


class MessageRepository:
    """Encapsulate persistence operations for session messages."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def count_by_session_id(self, session_id: str) -> int:
        """Return the total number of transcript messages in a session."""
        return self.db.query(Message).filter(Message.session_id == session_id).count()

    def list_by_session_id(self, session_id: str, *, offset: int = 0, limit: int = 20) -> list[Message]:
        """Return a paginated transcript ordered by creation time."""
        return (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_recent_by_session_id(self, session_id: str, *, limit: int = 8) -> list[Message]:
        """Return the most recent transcript slice in chronological order."""
        recent_messages = (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(recent_messages))

    def create(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        trace_id: str | None = None,
        message_id: str | None = None,
    ) -> Message:
        """Create and persist a new transcript message."""
        message = Message(
            message_id=message_id or generate_message_id(),
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            trace_id=trace_id,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message
