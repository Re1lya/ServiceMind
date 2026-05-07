from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.router import api_router
from app.core.config import settings
from app.db.session import init_db
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_context import RequestContextMiddleware

FRONTEND_DIST_ROOT = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app() -> FastAPI:
    """Create FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        version="0.1.0",
        description="Backend skeleton for the ServiceMind intelligent customer service system.",
    )

    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api")
    app.state.skip_db_init = False

    if FRONTEND_DIST_ROOT.exists():
        app.mount("/console", StaticFiles(directory=FRONTEND_DIST_ROOT, html=True), name="console")

        @app.get("/", include_in_schema=False)
        async def root_redirect() -> RedirectResponse:
            return RedirectResponse(url="/console/")

    @app.on_event("startup")
    def on_startup() -> None:
        if app.state.skip_db_init:
            return
        init_db()

    return app


app = create_app()

# TODO: register middleware, exception handlers, startup hooks, and observability.
