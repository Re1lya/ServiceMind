"""Logistics query tool module."""

from __future__ import annotations

import re
from typing import Any

from app.tools.base import ToolExecutionResult

_ORDER_NO_PATTERN = re.compile(r"\b([A-Z]{2,}[0-9]{4,}|[0-9]{8,})\b")
_TRACKING_NO_PATTERN = re.compile(r"\b(SF[0-9]{8,}|YT[0-9]{8,}|JD[0-9]{8,}|TRACK[0-9]{6,})\b")

_MOCK_LOGISTICS: list[dict[str, Any]] = [
    {
        "order_no": "ORD2026043001",
        "tracking_no": "SF2026043001",
        "user_id": "u_order_001",
        "carrier": "SF Express",
        "status": "in_transit",
        "estimated_delivery_at": "2026-05-02T18:00:00+08:00",
        "current_node": "上海转运中心已发出",
        "timeline": [
            "2026-04-30 09:10 商家已发货",
            "2026-04-30 18:20 上海转运中心已揽收",
            "2026-05-01 08:05 上海转运中心已发出",
        ],
    },
    {
        "order_no": "ORD2026043002",
        "tracking_no": "JD2026043002",
        "user_id": "u_order_002",
        "carrier": "JD Logistics",
        "status": "out_for_delivery",
        "estimated_delivery_at": "2026-05-01T20:00:00+08:00",
        "current_node": "快递员派送中",
        "timeline": [
            "2026-04-29 16:10 商家已发货",
            "2026-04-30 11:40 北京快件中心已出库",
            "2026-05-01 09:20 目的站点已到达",
            "2026-05-01 13:05 快递员派送中",
        ],
    },
    {
        "order_no": "ORD2026043003",
        "tracking_no": "YT2026043003",
        "user_id": "u_multi_001",
        "carrier": "YTO Express",
        "status": "processing",
        "estimated_delivery_at": "2026-05-03T18:00:00+08:00",
        "current_node": "订单待出库",
        "timeline": [
            "2026-04-27 09:30 订单支付成功",
            "2026-04-27 10:10 仓库处理中",
        ],
    },
    {
        "order_no": "ORD2026043004",
        "tracking_no": "SF2026043004",
        "user_id": "u_multi_001",
        "carrier": "SF Express",
        "status": "in_transit",
        "estimated_delivery_at": "2026-05-04T18:00:00+08:00",
        "current_node": "杭州分拨中心运输中",
        "timeline": [
            "2026-04-30 09:10 商家已发货",
            "2026-04-30 20:10 杭州分拨中心已揽收",
            "2026-05-01 07:50 杭州分拨中心运输中",
        ],
    },
]


def _extract_order_no(text: str) -> str | None:
    match = _ORDER_NO_PATTERN.search((text or "").upper())
    if not match:
        return None
    return match.group(1)


def _extract_tracking_no(text: str) -> str | None:
    match = _TRACKING_NO_PATTERN.search((text or "").upper())
    if not match:
        return None
    return match.group(1)


def _serialize_logistics(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_no": item["order_no"],
        "tracking_no": item["tracking_no"],
        "carrier": item["carrier"],
        "status": item["status"],
        "estimated_delivery_at": item["estimated_delivery_at"],
        "current_node": item["current_node"],
        "timeline": item["timeline"],
    }


def execute_logistics_query(
    *,
    query: str,
    user_id: str | None = None,
    order_no: str | None = None,
    tracking_no: str | None = None,
) -> ToolExecutionResult:
    """Resolve a mock logistics lookup for the MVP tool-calling chain."""
    resolved_order_no = order_no or _extract_order_no(query)
    resolved_tracking_no = tracking_no or _extract_tracking_no(query)

    matched: dict[str, Any] | None = None
    if resolved_tracking_no:
        normalized_tracking_no = resolved_tracking_no.upper()
        matched = next(
            (
                item
                for item in _MOCK_LOGISTICS
                if item["tracking_no"] == normalized_tracking_no and (user_id is None or item["user_id"] == user_id)
            ),
            None,
        )
    elif resolved_order_no:
        normalized_order_no = resolved_order_no.upper()
        matched = next(
            (
                item
                for item in _MOCK_LOGISTICS
                if item["order_no"] == normalized_order_no and (user_id is None or item["user_id"] == user_id)
            ),
            None,
        )

    if matched is not None:
        return ToolExecutionResult(
            tool_name="logistics_query",
            status="success",
            message="已查到匹配的物流信息。",
            data=_serialize_logistics(matched),
        )

    if resolved_order_no or resolved_tracking_no:
        return ToolExecutionResult(
            tool_name="logistics_query",
            status="not_found",
            message="未查到匹配的物流信息，请确认订单号或运单号是否正确。",
        )

    if not user_id:
        return ToolExecutionResult(
            tool_name="logistics_query",
            status="needs_input",
            message="我可以帮你查物流，请提供订单号、运单号，或者在请求里带上 user_id。",
        )

    user_shipments = [item for item in _MOCK_LOGISTICS if item["user_id"] == user_id]
    if not user_shipments:
        return ToolExecutionResult(
            tool_name="logistics_query",
            status="not_found",
            message="当前用户下没有查到可用物流记录，请确认 user_id 是否正确。",
        )
    if len(user_shipments) > 1:
        return ToolExecutionResult(
            tool_name="logistics_query",
            status="needs_input",
            message="当前用户匹配到多笔物流记录，请补充订单号或运单号以便我精确查询。",
        )

    return ToolExecutionResult(
        tool_name="logistics_query",
        status="success",
        message="已按 user_id 匹配到物流信息。",
        data=_serialize_logistics(user_shipments[0]),
    )
