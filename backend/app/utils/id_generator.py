"""ID generation helper module."""

from __future__ import annotations

import uuid


def generate_session_id() -> str:
    """Generate a stable public identifier for chat sessions."""
    return f"sess_{uuid.uuid4().hex}"


def generate_message_id() -> str:
    """Generate a stable public identifier for chat messages."""
    return f"msg_{uuid.uuid4().hex}"


def generate_document_id() -> str:
    """Generate a stable public identifier for knowledge documents."""
    return f"doc_{uuid.uuid4().hex}"


def generate_tool_log_id() -> str:
    """Generate a stable public identifier for tool invocation logs."""
    return f"tlog_{uuid.uuid4().hex}"
