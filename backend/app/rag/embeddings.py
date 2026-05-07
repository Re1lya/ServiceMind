"""Embedding model module."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

import httpx

from app.core.config import settings


DEFAULT_EMBEDDING_DIMENSION = 384
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


def build_local_embedding(text: str, *, dimension: int = DEFAULT_EMBEDDING_DIMENSION) -> list[float]:
    """Build a deterministic local hashing embedding for offline MVP retrieval."""
    vector = [0.0] * dimension
    tokens = _tokenize(text)
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    return _normalize(vector)


def _extract_embedding(response_payload: dict[str, Any]) -> list[float]:
    data = response_payload.get("data") or []
    if not data:
        return []
    embedding = data[0].get("embedding")
    if not isinstance(embedding, list):
        return []
    return [float(value) for value in embedding]


def _should_use_remote_embedding() -> bool:
    api_base = settings.resolved_embedding_api_base
    api_key = settings.resolved_embedding_api_key
    if not api_base or not api_key:
        return False
    if api_key in {"your_api_key", "test"}:
        return False
    return True


def embed_text(text: str) -> list[float]:
    """Return an embedding for a single text, falling back to local hashing."""
    if not _should_use_remote_embedding():
        return build_local_embedding(text)

    try:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.resolved_embedding_api_key}"}
        payload = {
            "model": settings.embedding_model_name,
            "input": text,
        }
        with httpx.Client(timeout=min(settings.embedding_timeout_seconds, 8.0)) as client:
            response = client.post(
                f"{settings.resolved_embedding_api_base}/embeddings",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        embedding = _extract_embedding(response.json())
        return _normalize(embedding) if embedding else build_local_embedding(text)
    except Exception:
        return build_local_embedding(text)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Return embeddings for multiple texts."""
    return [embed_text(text) for text in texts]
