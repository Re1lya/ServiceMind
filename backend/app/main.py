from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Create FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        version="0.1.0",
        description="Backend skeleton for the ServiceMind intelligent customer service system.",
    )

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()

# TODO: register middleware, exception handlers, startup hooks, and observability.
