"""Intent router module."""

from __future__ import annotations


def route_user_intent(message: str) -> str:
    """Return a coarse-grained route label for the MVP closed loop."""
    normalized = message.strip()
    if "物流" in normalized:
        return "logistics_query"
    if "订单" in normalized:
        return "order_query"
    if any(keyword in normalized for keyword in ("退款", "发票", "规则", "政策", "售后", "优惠", "会员")):
        return "knowledge_qa"
    return "general_chat"
