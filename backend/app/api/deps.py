"""Shared API dependency definitions."""

from app.db.session import get_db

__all__ = ["get_db"]
