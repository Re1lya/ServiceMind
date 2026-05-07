from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.common import BaseResponse
from app.schemas.kb import (
    KnowledgeRebuildResponseData,
    KnowledgeSearchResponseData,
    KnowledgeUploadRequest,
    KnowledgeUploadResponseData,
)
from app.services.kb_service import rebuild_knowledge_index as rebuild_knowledge_index_service
from app.services.kb_service import search_knowledge as search_knowledge_service
from app.services.kb_service import upload_knowledge_document as upload_knowledge_document_service

router = APIRouter()


@router.post("/upload")
async def upload_knowledge_document(
    payload: KnowledgeUploadRequest,
    db: Session = Depends(get_db),
) -> BaseResponse[KnowledgeUploadResponseData]:
    """Upload a single knowledge document into the MVP retriever store."""
    return BaseResponse(data=upload_knowledge_document_service(db, payload))


@router.post("/rebuild")
async def rebuild_knowledge_index(db: Session = Depends(get_db)) -> BaseResponse[KnowledgeRebuildResponseData]:
    """Rebuild the MVP knowledge index from files under data/raw."""
    source_dir = Path(__file__).resolve().parents[5] / "data" / "raw"
    return BaseResponse(data=rebuild_knowledge_index_service(db, source_dir=source_dir))


@router.get("/search")
async def search_knowledge(
    query: str = Query(..., min_length=1),
    top_k: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
) -> BaseResponse[KnowledgeSearchResponseData]:
    """Search indexed knowledge documents with a lightweight lexical retriever."""
    return BaseResponse(data=search_knowledge_service(db, query=query, top_k=top_k))


# TODO: support document parsing, indexing tasks, metadata management, and source tracing.
