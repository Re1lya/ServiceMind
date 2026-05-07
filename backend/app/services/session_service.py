"""Session service module."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.repositories.message_repository import MessageRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.session import PaginationMeta, SessionDetailData, SessionMessageItem


def get_session_detail(db: Session, session_id: str, *, page: int = 1, page_size: int = 20) -> SessionDetailData:
    """Load a session and its transcript for API delivery."""
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    session_repository = SessionRepository(db)
    message_repository = MessageRepository(db)

    session = session_repository.get_by_session_id(session_id)
    if session is None:
        raise NotFoundException(
            message="session not found",
            detail={"session_id": session_id},
        )

    total_messages = message_repository.count_by_session_id(session_id)
    messages = [
        SessionMessageItem.model_validate(message)
        for message in message_repository.list_by_session_id(session_id, offset=offset, limit=page_size)
    ]

    return SessionDetailData(
        session_id=session.session_id,
        user_id=session.user_id,
        channel=session.channel,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total_messages,
            has_more=offset + len(messages) < total_messages,
        ),
        messages=messages,
    )
