from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Temporary health endpoint for local boot verification."""
    return {"status": "todo"}


# TODO: replace with real health checks for database, redis, model service, and vector store.
