from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeUploadRequest(BaseModel):
    """Structured knowledge document upload payload."""

    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    source_type: str = Field(default="text")
    source_path: str | None = None


class KnowledgeDocumentData(BaseModel):
    """Serialized knowledge document metadata."""

    document_id: str
    title: str
    source_type: str
    source_path: str | None
    status: str
    created_at: datetime


class KnowledgeUploadResponseData(BaseModel):
    """Upload result payload."""

    document: KnowledgeDocumentData
    indexed_count: int = 1
    chunk_count: int = 1
    vector_count: int = 0


class KnowledgeRebuildResponseData(BaseModel):
    """Knowledge rebuild result payload."""

    indexed_count: int
    vector_count: int = 0


class KnowledgeSearchResultItem(BaseModel):
    """Single retrieved knowledge hit."""

    document_id: str
    title: str
    source_type: str
    source_path: str | None = None
    score: float
    snippet: str


class KnowledgeSearchResponseData(BaseModel):
    """Search endpoint response payload."""

    query: str
    hits: list[KnowledgeSearchResultItem]
