from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


from app.models import KnowledgeDocument, Message, Session, ToolLog

__all__ = ["Base", "KnowledgeDocument", "Message", "Session", "ToolLog"]
