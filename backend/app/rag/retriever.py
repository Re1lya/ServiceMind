"""Retriever module."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import math
import re

from sqlalchemy.orm import Session

from app.repositories.kb_repository import KnowledgeBaseRepository
from app.rag.vector_store import search_vector_store


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
LATIN_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
CHINESE_SEQUENCE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")

LEXICAL_STOPWORDS = {
    "一个",
    "一般",
    "什么",
    "信息",
    "哪些",
    "多久",
    "如何",
    "平台",
    "怎么",
    "怎么办",
    "是否",
    "服务",
    "用户",
    "规则",
    "说明",
    "这个",
    "这些",
    "需要",
    "支持",
    "商品",
    "订单",
    "问题",
    "处理",
    "可以",
    "不能",
}
MIN_VECTOR_SCORE = 0.18
MIN_LEXICAL_SCORE = 2.0
MIN_DISTINCT_TERMS = 2


@dataclass(slots=True)
class RetrievedDocument:
    """Single retrieved knowledge hit with a lightweight lexical score."""

    document_id: str
    title: str
    source_type: str
    source_path: str | None
    score: float
    snippet: str
    content: str


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _tokenize_lexical_terms(text: str) -> list[str]:
    """Extract meaningful lexical terms, preferring jieba and falling back to n-grams."""
    terms: set[str] = {token.lower() for token in LATIN_TOKEN_PATTERN.findall(text)}
    for sequence in CHINESE_SEQUENCE_PATTERN.findall(text):
        jieba_terms = _tokenize_chinese_with_jieba(sequence)
        terms.update(jieba_terms or _tokenize_chinese_ngrams(sequence))
    return sorted(terms, key=lambda item: (-len(item), item))


def _tokenize_chinese_with_jieba(sequence: str) -> set[str]:
    """Tokenize Chinese text with jieba when the dependency is installed."""
    try:
        jieba = importlib.import_module("jieba")
    except ImportError:
        return set()

    terms: set[str] = set()
    for token in jieba.cut(sequence, HMM=True):
        normalized = token.strip().lower()
        if len(normalized) < 2 or normalized in LEXICAL_STOPWORDS:
            continue
        terms.add(normalized)
    return terms


def _tokenize_chinese_ngrams(sequence: str) -> set[str]:
    """Build 2-4 character Chinese n-grams as a fallback tokenizer."""
    terms: set[str] = set()
    length = len(sequence)
    for size in range(2, min(5, length + 1)):
        for start in range(0, length - size + 1):
            term = sequence[start : start + size]
            if term not in LEXICAL_STOPWORDS:
                terms.add(term)
    return terms


def _build_term_weights(query: str, candidates) -> dict[str, float]:
    """Build lightweight IDF-style weights for query terms within current candidates."""
    query_terms = _tokenize_lexical_terms(query)
    if not query_terms:
        return {}
    candidate_count = len(candidates) or 1
    weights: dict[str, float] = {}
    for token in query_terms:
        document_frequency = sum(
            1
            for document in candidates
            if token in document.title or token in document.content
        )
        if document_frequency <= 0:
            continue
        weights[token] = 1.0 + math.log((candidate_count + 1) / (document_frequency + 1))
    return weights


def _score_document(
    query: str,
    *,
    title: str,
    content: str,
    term_weights: dict[str, float] | None = None,
) -> float:
    query_terms = list(term_weights.keys()) if term_weights is not None else _tokenize_lexical_terms(query)
    if not query_terms:
        return 0.0

    score = 8.0 if _has_title_match(query, title) else 0.0
    matched_terms = 0
    for token in query_terms:
        weight = term_weights[token] if term_weights is not None else 1.0
        matched = False
        if token in title:
            score += 3.0 * weight
            matched = True
        if token in content:
            score += weight
            matched = True
        if matched:
            matched_terms += 1
    score += matched_terms * 2.5
    return score


def _has_title_match(query: str, title: str) -> bool:
    """Return whether a short query directly names the document title."""
    normalized_query = query.strip().lower()
    normalized_title = title.strip().lower()
    return bool(normalized_query and normalized_title and (normalized_query in normalized_title or normalized_title in normalized_query))


def _count_matched_terms(
    query: str,
    *,
    title: str,
    content: str,
    term_weights: dict[str, float] | None = None,
) -> int:
    query_terms = list(term_weights.keys()) if term_weights is not None else _tokenize_lexical_terms(query)
    return sum(1 for token in query_terms if token in title or token in content)


def _build_snippet(content: str, query: str, *, max_length: int = 160) -> str:
    query_terms = _tokenize_lexical_terms(query)
    for token in query_terms:
        if token and token in content:
            index = content.index(token)
            start = max(0, index - 30)
            end = min(len(content), index + max_length)
            return content[start:end].strip()
    return content[:max_length].strip()


def retrieve_documents(db: Session, query: str, *, top_k: int = 3) -> list[RetrievedDocument]:
    """Return top knowledge matches, preferring FAISS vector search with lexical fallback."""
    repository = KnowledgeBaseRepository(db)
    indexed_documents = repository.list_indexed_documents()
    if not indexed_documents:
        return []
    indexed_document_ids = {document.document_id for document in indexed_documents}
    term_weights = _build_term_weights(query, indexed_documents)

    vector_hits = search_vector_store(query, top_k=max(top_k, 8))
    if vector_hits:
        converted_hits: list[RetrievedDocument] = []
        for hit in vector_hits:
            if hit.score < MIN_VECTOR_SCORE or hit.document_id not in indexed_document_ids:
                continue
            matched_terms = _count_matched_terms(
                query,
                title=hit.title,
                content=hit.content,
                term_weights=term_weights,
            )
            if matched_terms < MIN_DISTINCT_TERMS and hit.score < 0.3:
                if not _has_title_match(query, hit.title):
                    continue
            lexical_score = _score_document(
                query,
                title=hit.title,
                content=hit.content,
                term_weights=term_weights,
            )
            if lexical_score < MIN_LEXICAL_SCORE:
                continue
            converted_hits.append(
                RetrievedDocument(
                    document_id=hit.document_id,
                    title=hit.title,
                    source_type=hit.source_type,
                    source_path=hit.source_path,
                    score=hit.score + lexical_score,
                    snippet=_build_snippet(hit.content, query),
                    content=hit.content,
                )
            )
        converted_hits.sort(key=lambda item: (-item.score, item.title))
        if converted_hits:
            return converted_hits[:top_k]

    return retrieve_documents_lexical(
        db,
        query,
        top_k=top_k,
        candidates=indexed_documents,
        term_weights=term_weights,
    )


def retrieve_documents_lexical(
    db: Session,
    query: str,
    *,
    top_k: int = 3,
    candidates=None,
    term_weights: dict[str, float] | None = None,
) -> list[RetrievedDocument]:
    """Return top lexical knowledge matches for the current query."""
    if candidates is None:
        repository = KnowledgeBaseRepository(db)
        candidates = repository.list_indexed_documents()
    if term_weights is None:
        term_weights = _build_term_weights(query, candidates)

    scored_hits: list[RetrievedDocument] = []
    for document in candidates:
        score = _score_document(
            query,
            title=document.title,
            content=document.content,
            term_weights=term_weights,
        )
        matched_terms = _count_matched_terms(
            query,
            title=document.title,
            content=document.content,
            term_weights=term_weights,
        )
        if matched_terms < MIN_DISTINCT_TERMS:
            if not _has_title_match(query, document.title):
                continue
        if score < MIN_LEXICAL_SCORE:
            continue
        scored_hits.append(
            RetrievedDocument(
                document_id=document.document_id,
                title=document.title,
                source_type=document.source_type,
                source_path=document.source_path,
                score=score,
                snippet=_build_snippet(document.content, query),
                content=document.content,
            )
        )

    scored_hits.sort(key=lambda item: (-item.score, item.title))
    return scored_hits[:top_k]
