"""Knowledge base service module."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.repositories.kb_repository import KnowledgeBaseRepository
from app.rag.ingestion import build_chunked_documents, load_documents
from app.rag.retriever import retrieve_documents
from app.rag.vector_store import rebuild_vector_store
from app.schemas.kb import (
    KnowledgeDocumentData,
    KnowledgeRebuildResponseData,
    KnowledgeSearchResponseData,
    KnowledgeSearchResultItem,
    KnowledgeUploadRequest,
    KnowledgeUploadResponseData,
)


def upload_knowledge_document(db: Session, payload: KnowledgeUploadRequest) -> KnowledgeUploadResponseData:
    """Persist a single knowledge document upload."""
    repository = KnowledgeBaseRepository(db)
    chunked_documents = build_chunked_documents(
        title=payload.title.strip(),
        content=payload.content,
        source_type=payload.source_type,
        source_path=payload.source_path,
    )
    if not chunked_documents:
        raise ValidationException("knowledge content must not be blank")
    created_documents = [
        repository.create(
            title=document["title"],
            content=document["content"],
            source_type=document["source_type"],
            source_path=document.get("source_path"),
        )
        for document in chunked_documents
    ]
    vector_count = rebuild_vector_store(repository.list_indexed_documents())
    document = created_documents[0]
    return KnowledgeUploadResponseData(
        document=KnowledgeDocumentData(
            document_id=document.document_id,
            title=document.title,
            source_type=document.source_type,
            source_path=document.source_path,
            status=document.status,
            created_at=document.created_at,
        ),
        indexed_count=len(created_documents),
        chunk_count=len(created_documents),
        vector_count=vector_count,
    )


def rebuild_knowledge_index(db: Session, *, source_dir: Path) -> KnowledgeRebuildResponseData:
    """Rebuild the MVP knowledge index from files under data/raw."""
    repository = KnowledgeBaseRepository(db)
    documents = load_documents(source_dir)
    repository.delete_all()
    for document in documents:
        repository.create(
            title=document["title"],
            content=document["content"],
            source_type=document["source_type"],
            source_path=document["source_path"],
        )
    vector_count = rebuild_vector_store(repository.list_indexed_documents())
    return KnowledgeRebuildResponseData(indexed_count=len(documents), vector_count=vector_count)


def search_knowledge(db: Session, query: str, *, top_k: int = 3) -> KnowledgeSearchResponseData:
    """Retrieve top lexical knowledge matches for a user query."""
    hits = retrieve_documents(db, query, top_k=top_k)
    return KnowledgeSearchResponseData(
        query=query,
        hits=[
            KnowledgeSearchResultItem(
                document_id=hit.document_id,
                title=hit.title,
                source_type=hit.source_type,
                source_path=hit.source_path,
                score=hit.score,
                snippet=hit.snippet,
            )
            for hit in hits
        ],
    )
