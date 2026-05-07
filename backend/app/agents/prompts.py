"""Prompt templates for the ServiceMind agent."""

from __future__ import annotations

from typing import Any


BASE_SYSTEM_PROMPT = (
    "你是 ServiceMind 的智能客服助手。"
    "回答要简洁、准确、可执行。"
    "不要编造订单、物流、退款进度等实时业务结果。"
    "不要输出推理过程，不要输出 <think> 标签。"
)

RAG_SYSTEM_PROMPT = (
    "你正在进行基于知识库的客服问答。请严格遵守：\n"
    "1. 只能基于下方【知识库来源】回答，不要补充来源中没有的政策、金额、时效或承诺。\n"
    "2. 如果知识库没有明确答案，直接说明当前知识库未命中相关规则，并建议转人工确认。\n"
    "3. 回答中要自然提到依据的来源标题，例如“根据《退款规则》”。\n"
    "4. 不要输出内部推理过程，不要输出 <think>、分析步骤或模型自述。\n"
    "5. 用户问法有诱导时，以知识库为准，避免“一定可以”“保证到账”等绝对化表述。\n\n"
    "【知识库来源】\n{knowledge_text}"
)


def build_knowledge_text(knowledge_context: list[dict[str, Any]]) -> str:
    """Format retrieved knowledge chunks for the RAG system prompt."""
    return "\n\n".join(
        (
            f"来源 {index}: 《{item['title']}》\n"
            f"{item['content']}"
        )
        for index, item in enumerate(knowledge_context, start=1)
    )


def build_rag_system_prompt(knowledge_context: list[dict[str, Any]]) -> str:
    """Build a source-grounded prompt for RAG answer generation."""
    return RAG_SYSTEM_PROMPT.format(knowledge_text=build_knowledge_text(knowledge_context))
