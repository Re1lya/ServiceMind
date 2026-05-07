"""Minimal OpenAI-compatible client for DeepSeek and Ollama."""

from __future__ import annotations

from functools import lru_cache
import re
from typing import Any

import httpx

from app.core.config import Settings, settings


THINKING_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


class OpenAICompatibleClient:
    """Lightweight HTTP client for chat and embedding requests."""

    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        default_model: str,
        timeout_seconds: float,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        stream: bool = False,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if extra_body:
            payload.update(extra_body)

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def create_embeddings(
        self,
        inputs: str | list[str],
        *,
        model: str,
        api_base: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "input": inputs,
        }
        if extra_body:
            payload.update(extra_body)

        headers = {"Content-Type": "application/json"}
        effective_key = api_key if api_key is not None else self.api_key
        if effective_key:
            headers["Authorization"] = f"Bearer {effective_key}"

        async with httpx.AsyncClient(timeout=timeout_seconds or self.timeout_seconds) as client:
            response = await client.post(
                f"{(api_base or self.api_base).rstrip('/')}/embeddings",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()


def strip_thinking_blocks(text: str) -> str:
    """Remove reasoning blocks emitted by local thinking models such as Qwen3."""
    cleaned = THINKING_BLOCK_PATTERN.sub("", text)
    return cleaned.replace("<think>", "").replace("</think>", "").strip()


def extract_chat_text(response_payload: dict[str, Any], *, strip_thinking: bool = True) -> str:
    """Extract assistant text from an OpenAI-compatible chat response."""
    choices = response_payload.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()
        return strip_thinking_blocks(text) if strip_thinking else text

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_value = item.get("text")
                if isinstance(text_value, str):
                    text_parts.append(text_value)
        text = "".join(text_parts).strip()
        return strip_thinking_blocks(text) if strip_thinking else text

    return ""


@lru_cache
def get_llm_client(current_settings: Settings = settings) -> OpenAICompatibleClient:
    """Create a cached client using current application settings."""
    return OpenAICompatibleClient(
        api_base=current_settings.resolved_llm_api_base,
        api_key=current_settings.resolved_llm_api_key,
        default_model=current_settings.llm_model_name,
        timeout_seconds=current_settings.llm_timeout_seconds,
    )
