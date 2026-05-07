"""Base tool abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolExecutionResult:
    """Structured tool-layer result."""

    tool_name: str
    status: str
    message: str
    data: dict[str, Any] | None = None
