from fastapi import APIRouter

router = APIRouter()


@router.post("/upload")
async def upload_knowledge_document() -> dict[str, str]:
    """Placeholder knowledge base upload endpoint."""
    return {"message": "TODO: implement knowledge upload"}


@router.post("/rebuild")
async def rebuild_knowledge_index() -> dict[str, str]:
    """Placeholder knowledge base rebuild endpoint."""
    return {"message": "TODO: implement index rebuild"}


# TODO: support document parsing, indexing tasks, metadata management, and source tracing.
