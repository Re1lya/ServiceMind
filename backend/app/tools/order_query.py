"""Order query tool module."""

from __future__ import annotations

import re
from typing import Any

from app.tools.base import ToolExecutionResult

_ORDER_NO_PATTERN = re.compile(r"\b([A-Z]{2,}[0-9]{4,}|[0-9]{8,})\b")

_MOCK_ORDERS: list[dict[str, Any]] = [
    {
        "order_no": "ORD2026043001",
        "user_id": "u_order_001",
        "status": "paid",
        "amount": 129.90,
        "currency": "CNY",
        "item_count": 2,
        "created_at": "2026-04-29T10:30:00+08:00",
        "estimated_delivery_at": "2026-05-02T18:00:00+08:00",
        "summary": "蓝牙耳机 x1，保护壳 x1",
    },
    {
        "order_no": "ORD2026043002",
        "user_id": "u_order_002",
        "status": "shipped",
        "amount": 399.00,
        "currency": "CNY",
        "item_count": 1,
        "created_at": "2026-04-28T15:00:00+08:00",
        "estimated_delivery_at": "2026-05-01T20:00:00+08:00",
        "summary": "智能手表 x1",
    },
    {
        "order_no": "ORD2026043003",
        "user_id": "u_multi_001",
        "status": "processing",
        "amount": 59.00,
        "currency": "CNY",
        "item_count": 1,
        "created_at": "2026-04-27T09:15:00+08:00",
        "estimated_delivery_at": "2026-05-03T18:00:00+08:00",
        "summary": "数据线 x2",
    },
    {
        "order_no": "ORD2026043004",
        "user_id": "u_multi_001",
        "status": "paid",
        "amount": 219.00,
        "currency": "CNY",
        "item_count": 1,
        "created_at": "2026-04-30T08:45:00+08:00",
        "estimated_delivery_at": "2026-05-04T18:00:00+08:00",
        "summary": "路由器 x1",
    },
]


def _extract_order_no(text: str) -> str | None:
    """Parse a likely order number from free-form user input."""
    match = _ORDER_NO_PATTERN.search((text or "").upper())
    if not match:
        return None
    return match.group(1)


def _serialize_order(order: dict[str, Any]) -> dict[str, Any]:
    """Return a stable public payload for the matched order."""
    return {
        "order_no": order["order_no"],
        "status": order["status"],
        "amount": order["amount"],
        "currency": order["currency"],
        "item_count": order["item_count"],
        "created_at": order["created_at"],
        "estimated_delivery_at": order["estimated_delivery_at"],
        "summary": order["summary"],
    }


def execute_order_query(*, query: str, user_id: str | None = None, order_no: str | None = None) -> ToolExecutionResult:
    """Resolve a mock order lookup for the MVP tool-calling chain."""
    resolved_order_no = order_no or _extract_order_no(query)
    if resolved_order_no:
        normalized_order_no = resolved_order_no.upper()
        matched = next(
            (
                item
                for item in _MOCK_ORDERS
                if item["order_no"] == normalized_order_no and (user_id is None or item["user_id"] == user_id)
            ),
            None,
        )
        if matched is None:
            return ToolExecutionResult(
                tool_name="order_query",
                status="not_found",
                message="未查到匹配的订单，请确认订单号是否正确，或确认它是否属于当前用户。",
            )
        return ToolExecutionResult(
            tool_name="order_query",
            status="success",
            message="已查到匹配订单。",
            data=_serialize_order(matched),
        )

    if not user_id:
        return ToolExecutionResult(
            tool_name="order_query",
            status="needs_input",
            message="我可以帮你查订单，请提供订单号，或者在请求里带上 user_id。",
        )

    user_orders = [item for item in _MOCK_ORDERS if item["user_id"] == user_id]
    if not user_orders:
        return ToolExecutionResult(
            tool_name="order_query",
            status="not_found",
            message="当前用户下没有查到可用订单，请确认 user_id 是否正确。",
        )
    if len(user_orders) > 1:
        return ToolExecutionResult(
            tool_name="order_query",
            status="needs_input",
            message="当前用户匹配到多笔订单，请补充订单号以便我精确查询。",
        )
    return ToolExecutionResult(
        tool_name="order_query",
        status="success",
        message="已按 user_id 匹配到订单。",
        data=_serialize_order(user_orders[0]),
    )
