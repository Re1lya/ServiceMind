"""Monitoring and health-check service module."""

from __future__ import annotations

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.db.redis import get_redis_client
from app.db.session import engine
from app.schemas.common import HealthStatusData


def check_database() -> str:
    """Return database health status using a lightweight SELECT 1 probe."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "down"


def check_redis() -> str:
    """Return Redis health status using a PING probe."""
    try:
        if get_redis_client().ping():
            return "ok"
        return "down"
    except Exception:
        return "down"


async def check_llm() -> str:
    """Return LLM endpoint health status using a lightweight models probe."""
    if not settings.resolved_llm_api_base:
        return "unknown"

    headers = {"Content-Type": "application/json"}
    if settings.resolved_llm_api_key:
        headers["Authorization"] = f"Bearer {settings.resolved_llm_api_key}"

    try:
        async with httpx.AsyncClient(timeout=min(settings.llm_timeout_seconds, 5.0)) as client:
            response = await client.get(
                f"{settings.resolved_llm_api_base}/models",
                headers=headers,
            )
            response.raise_for_status()
        return "ok"
    except Exception:
        return "down"


async def build_health_status(*, trace_id: str | None = None) -> HealthStatusData:
    """Assemble the current health snapshot for the API and core dependencies."""
    components = {
        "api": "ok",
        "database": check_database(),
        "redis": check_redis(),
        "llm": await check_llm(),
    }
    status = "degraded" if any(value == "down" for value in components.values()) else "ok"
    return HealthStatusData(
        app_name=settings.app_name,
        app_env=settings.app_env,
        status=status,
        trace_id=trace_id,
        components=components,
    )
