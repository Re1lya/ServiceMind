"""Chat service module."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.orchestrator import run_chat_flow_with_context
from app.agents.router import route_user_intent
from app.core.exceptions import BusinessException
from app.repositories.message_repository import MessageRepository
from app.repositories.session_repository import SessionRepository
from app.rag.retriever import retrieve_documents
from app.schemas.chat import ChatRequest, ChatResponseData, KnowledgeSourceData
from app.schemas.tool import LogisticsQueryResultData, OrderQueryResultData, ToolInvocationResponseData
from app.services.tool_service import ToolService

MAX_CONTEXT_MESSAGES = 8
MAX_KNOWLEDGE_HITS = 3


def _build_history_messages(message_rows) -> list[dict[str, Any]]:
    """Convert transcript rows into LLM-ready history messages."""
    history_messages: list[dict[str, Any]] = []
    for row in message_rows:
        if row.role not in {"user", "assistant", "system"}:
            continue
        history_messages.append({"role": row.role, "content": row.content})
    return history_messages


def _build_knowledge_sources(retrieved_documents) -> list[KnowledgeSourceData]:
    """Convert retrieved documents into response-safe source metadata."""
    return [
        KnowledgeSourceData(
            document_id=document.document_id,
            title=document.title,
            source_type=document.source_type,
            source_path=document.source_path,
            score=document.score,
            snippet=document.snippet,
        )
        for document in retrieved_documents
    ]


def _build_order_tool_reply(invocation: ToolInvocationResponseData) -> str:
    """Convert a structured order tool result into assistant-facing text."""
    if invocation.status == "success" and isinstance(invocation.result, OrderQueryResultData):
        result = invocation.result
        return (
            f"已为你查到订单 {result.order_no}。"
            f"当前状态：{result.status}；"
            f"商品摘要：{result.summary}；"
            f"订单金额：{result.amount:.2f} {result.currency}；"
            f"商品数量：{result.item_count}；"
            f"预计送达时间：{result.estimated_delivery_at}。"
        )
    return invocation.message


def _build_logistics_tool_reply(invocation: ToolInvocationResponseData) -> str:
    """Convert a structured logistics tool result into assistant-facing text."""
    if invocation.status == "success" and isinstance(invocation.result, LogisticsQueryResultData):
        result = invocation.result
        latest_timeline = result.timeline[-1] if result.timeline else result.current_node
        return (
            f"已为你查到订单 {result.order_no} 的物流信息。"
            f"承运方：{result.carrier}；"
            f"当前物流状态：{result.status}；"
            f"最新节点：{result.current_node}；"
            f"最近更新：{latest_timeline}；"
            f"预计送达时间：{result.estimated_delivery_at}。"
        )
    return invocation.message


def _build_tool_failure_reply(route: str) -> str:
    """Return a user-facing fallback when the tool layer is unavailable."""
    if route == "order_query":
        return "订单查询服务暂时不可用，我已经记录了你的问题。请稍后重试，或提供订单号后由人工继续协助。"
    if route == "logistics_query":
        return "物流查询服务暂时不可用，我已经记录了你的问题。请稍后重试，或提供运单号后由人工继续协助。"
    return "当前工具服务暂时不可用，我已经记录了你的问题，请稍后重试。"


async def handle_chat_request(db: Session, payload: ChatRequest, *, trace_id: str | None = None) -> ChatResponseData:
    """Persist the user message, generate an MVP reply, and persist the reply."""
    session_repository = SessionRepository(db)
    message_repository = MessageRepository(db)

    if payload.session_id:
        session = session_repository.create_if_not_exists(
            session_id=payload.session_id,
            user_id=payload.user_id,
            channel=payload.channel,
        )
    else:
        session = session_repository.create(
            user_id=payload.user_id,
            channel=payload.channel,
        )

    user_message = message_repository.create(
        session_id=session.session_id,
        role="user",
        content=payload.message,
        trace_id=trace_id,
    )

    route = route_user_intent(payload.message)
    if route == "order_query":
        tool_service = ToolService(db)
        try:
            invocation = tool_service.execute_order_query(
                query=payload.message,
                user_id=payload.user_id,
                session_id=session.session_id,
                trace_id=trace_id,
            )
            reply = _build_order_tool_reply(invocation)
            answer_source = "tool"
        except BusinessException:
            reply = _build_tool_failure_reply(route)
            answer_source = "fallback"
        assistant_message = message_repository.create(
            session_id=session.session_id,
            role="assistant",
            content=reply,
            message_type="tool_result",
            trace_id=trace_id,
        )
        return ChatResponseData(
            session_id=session.session_id,
            reply=reply,
            route=route,
            answer_source=answer_source,
            trace_id=trace_id,
            user_message_id=user_message.message_id,
            assistant_message_id=assistant_message.message_id,
        )

    if route == "logistics_query":
        tool_service = ToolService(db)
        try:
            invocation = tool_service.execute_logistics_query(
                query=payload.message,
                user_id=payload.user_id,
                session_id=session.session_id,
                trace_id=trace_id,
            )
            reply = _build_logistics_tool_reply(invocation)
            answer_source = "tool"
        except BusinessException:
            reply = _build_tool_failure_reply(route)
            answer_source = "fallback"
        assistant_message = message_repository.create(
            session_id=session.session_id,
            role="assistant",
            content=reply,
            message_type="tool_result",
            trace_id=trace_id,
        )
        return ChatResponseData(
            session_id=session.session_id,
            reply=reply,
            route=route,
            answer_source=answer_source,
            trace_id=trace_id,
            user_message_id=user_message.message_id,
            assistant_message_id=assistant_message.message_id,
        )

    recent_messages = message_repository.list_recent_by_session_id(
        session.session_id,
        limit=MAX_CONTEXT_MESSAGES,
    )
    history_messages = _build_history_messages(recent_messages[:-1])
    knowledge_context: list[dict[str, str]] = []
    knowledge_sources: list[KnowledgeSourceData] = []
    if route in {"general_chat", "knowledge_qa"}:
        retrieved_documents = retrieve_documents(db, payload.message, top_k=MAX_KNOWLEDGE_HITS)
        knowledge_context = [
            {"title": item.title, "content": item.content}
            for item in retrieved_documents
        ]
        knowledge_sources = _build_knowledge_sources(retrieved_documents)

    reply, route, answer_source = await run_chat_flow_with_context(
        user_message=payload.message,
        history_messages=history_messages,
        knowledge_context=knowledge_context,
    )

    assistant_message = message_repository.create(
        session_id=session.session_id,
        role="assistant",
        content=reply,
        trace_id=trace_id,
    )

    return ChatResponseData(
        session_id=session.session_id,
        reply=reply,
        route=route,
        answer_source=answer_source,
        trace_id=trace_id,
        user_message_id=user_message.message_id,
        assistant_message_id=assistant_message.message_id,
        knowledge_sources=knowledge_sources if answer_source in {"rag_llm", "fallback"} else [],
    )
