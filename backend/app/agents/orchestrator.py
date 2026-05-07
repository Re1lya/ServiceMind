"""Main agent orchestrator module."""

from __future__ import annotations

import httpx
from typing import Any

from app.agents.prompts import BASE_SYSTEM_PROMPT, build_rag_system_prompt
from app.agents.router import route_user_intent
from app.core.config import settings
from app.core.llm import extract_chat_text, get_llm_client


def _build_fallback_reply(user_message: str, route: str) -> str:
    """Return a deterministic fallback reply when the LLM is unavailable."""
    if route == "order_query":
        return "我已经识别到这是订单相关问题。当前会话已记录，订单工具会在后续模块接入。"
    if route == "logistics_query":
        return "我已经识别到这是物流相关问题。当前会话已记录，物流工具会在后续模块接入。"
    if route == "knowledge_qa":
        return "我已经识别到这是知识问答类问题。当前会话已记录，如果模型暂时不可用，请稍后重试或转人工确认。"
    return f"已收到你的消息：{user_message}。当前会话记录闭环已完成，知识库与工具能力会在后续模块逐步接入。"


async def run_chat_flow(user_message: str) -> tuple[str, str, str]:
    """Return a model reply when available, otherwise fall back deterministically."""
    return await run_chat_flow_with_context(user_message=user_message, history_messages=[])


async def run_chat_flow_with_context(
    *,
    user_message: str,
    history_messages: list[dict[str, Any]],
    knowledge_context: list[dict[str, str]] | None = None,
) -> tuple[str, str, str]:
    """Return a model reply using recent transcript context when available."""
    route = route_user_intent(user_message)
    llm_client = get_llm_client()

    llm_messages: list[dict[str, Any]] = [{"role": "system", "content": BASE_SYSTEM_PROMPT}]
    if knowledge_context:
        route = "knowledge_qa"
        llm_messages.append(
            {
                "role": "system",
                "content": build_rag_system_prompt(knowledge_context),
            }
        )
    llm_messages.extend(history_messages)
    llm_messages.append({"role": "user", "content": user_message})

    try:
        response_payload = await llm_client.chat_completion(
            messages=llm_messages,
            temperature=0.2,
        )
        reply = extract_chat_text(response_payload, strip_thinking=settings.llm_strip_thinking)
        if reply:
            answer_source = "rag_llm" if knowledge_context else "llm"
            return reply, route, answer_source
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        pass

    return _build_fallback_reply(user_message, route), route, "fallback"
