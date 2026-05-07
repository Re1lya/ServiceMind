"""Session repository module."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.session import Session as SessionModel
from app.utils.id_generator import generate_session_id


class SessionRepository:
    """Encapsulate persistence operations for conversation sessions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_session_id(self, session_id: str) -> SessionModel | None:
        """Fetch a session by its public identifier."""
        return self.db.query(SessionModel).filter(SessionModel.session_id == session_id).first()

    def create(
        self,
        *,
        user_id: str | None = None,
        channel: str = "web",
        status: str = "active",
        session_id: str | None = None,
    ) -> SessionModel:
        """Create and persist a new session row."""
        session = SessionModel(
            session_id=session_id or generate_session_id(),
            user_id=user_id,
            channel=channel,
            status=status,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def create_if_not_exists(
        self,
        *,
        session_id: str,
        user_id: str | None = None,
        channel: str = "web",
    ) -> SessionModel:
        """Return an existing session or create it when absent."""
        existing = self.get_by_session_id(session_id)
        if existing:
            return existing
        return self.create(session_id=session_id, user_id=user_id, channel=channel)
