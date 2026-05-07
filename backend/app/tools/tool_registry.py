"""Tool registry module."""

from __future__ import annotations

from collections.abc import Callable

from app.core.exceptions import NotFoundException
from app.tools.logistics_query import execute_logistics_query
from app.tools.order_query import execute_order_query

ToolHandler = Callable[..., object]

_TOOL_REGISTRY: dict[str, ToolHandler] = {
    "order_query": execute_order_query,
    "logistics_query": execute_logistics_query,
}


def get_tool(tool_name: str) -> ToolHandler:
    """Return a registered tool handler or raise a business 404."""
    handler = _TOOL_REGISTRY.get(tool_name)
    if handler is None:
        raise NotFoundException(message=f"tool '{tool_name}' is not registered")
    return handler
