"""Knowledge base repository module."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.knowledge_document import KnowledgeDocument
from app.utils.id_generator import generate_document_id


class KnowledgeBaseRepository:
    """Encapsulate persistence operations for knowledge documents."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        title: str,
        content: str,
        source_type: str = "text",
        source_path: str | None = None,
        status: str = "indexed",
        document_id: str | None = None,
    ) -> KnowledgeDocument:
        """Persist a new knowledge document."""
        document = KnowledgeDocument(
            document_id=document_id or generate_document_id(),
            title=title,
            content=content,
            source_type=source_type,
            source_path=source_path,
            status=status,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def list_indexed_documents(self) -> list[KnowledgeDocument]:
        """Return all indexed knowledge documents."""
        return (
            self.db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.status == "indexed")
            .order_by(KnowledgeDocument.created_at.asc(), KnowledgeDocument.id.asc())
            .all()
        )

    def delete_all(self) -> None:
        """Delete all knowledge documents."""
        self.db.query(KnowledgeDocument).delete()
        self.db.commit()
