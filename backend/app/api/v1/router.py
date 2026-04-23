from fastapi import APIRouter

from app.api.v1.endpoints import chat, health, kb, sessions, tools

v1_router = APIRouter()
v1_router.include_router(health.router, tags=["health"])
v1_router.include_router(chat.router, prefix="/chat", tags=["chat"])
v1_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
v1_router.include_router(kb.router, prefix="/kb", tags=["knowledge-base"])
v1_router.include_router(tools.router, prefix="/tools", tags=["tools"])

# TODO: split routers further when modules become large.
