"""Offline answer quality evaluation script."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
from time import perf_counter
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEFAULT_DATASET_PATH = PROJECT_ROOT / "data" / "eval" / "answer_questions.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "reports" / "answer_eval_report.md"
MAX_ANSWER_CONTEXT_CHARS = 220


@dataclass(slots=True)
class AnswerEvalCase:
    """Single answer evaluation case."""

    case_id: str
    question: str
    category: str = "general"
    expected_source_title: str | None = None
    expected_source: str | None = None
    expected_keywords: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    expect_no_hit: bool = False


@dataclass(slots=True)
class AnswerEvalSource:
    """Single source used by an evaluated answer."""

    rank: int
    document_id: str
    title: str
    score: float
    snippet: str
    content: str


@dataclass(slots=True)
class GeneratedAnswer:
    """Deterministic answer produced for repeatable evaluation."""

    reply: str
    sources: list[AnswerEvalSource]
    answer_source: str


@dataclass(slots=True)
class AnswerEvalResult:
    """Per-case answer evaluation result."""

    case: AnswerEvalCase
    reply: str
    answer_source: str
    sources: list[AnswerEvalSource]
    latency_ms: float
    retrieval_latency_ms: float
    generation_latency_ms: float
    source_returned: bool
    source_matched: bool
    keyword_coverage: float
    forbidden_violations: list[str]
    grounded: bool
    no_hit_correct: bool | None


@dataclass(slots=True)
class AnswerEvalSummary:
    """Aggregate answer quality evaluation metrics."""

    mode: str
    total_cases: int
    positive_cases: int
    negative_cases: int
    top_k: int
    source_return_rate: float
    source_match_rate: float
    keyword_coverage: float
    forbidden_violation_rate: float
    groundedness_rate: float
    no_hit_accuracy: float | None
    average_latency_ms: float
    average_retrieval_latency_ms: float
    average_generation_latency_ms: float
    results: list[AnswerEvalResult]


def load_cases(dataset_path: Path) -> list[AnswerEvalCase]:
    """Load answer evaluation cases from JSON."""
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases: list[AnswerEvalCase] = []
    for item in payload:
        cases.append(
            AnswerEvalCase(
                case_id=item["id"],
                question=item["question"],
                category=item.get("category", "general"),
                expected_source_title=item.get("expected_source_title") or item.get("gold_title"),
                expected_source=item.get("expected_source") or item.get("gold_doc_id"),
                expected_keywords=list(item.get("expected_keywords") or []),
                must_not_include=list(item.get("must_not_include") or []),
                expect_no_hit=bool(item.get("expect_no_hit", False)),
            )
        )
    return cases


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _compact_content(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    if len(normalized) <= MAX_ANSWER_CONTEXT_CHARS:
        return normalized
    return normalized[:MAX_ANSWER_CONTEXT_CHARS].rstrip() + "..."


def _source_matches_case(source: AnswerEvalSource, case: AnswerEvalCase) -> bool:
    if case.expected_source and source.document_id == case.expected_source:
        return True
    if case.expected_source_title and source.title == case.expected_source_title:
        return True
    return False


def _keyword_coverage(reply: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 0.0
    normalized_reply = _normalize_text(reply)
    matched_count = sum(1 for keyword in expected_keywords if _normalize_text(keyword) in normalized_reply)
    return matched_count / len(expected_keywords)


def _find_forbidden_violations(reply: str, forbidden_phrases: list[str]) -> list[str]:
    normalized_reply = _normalize_text(reply)
    return [phrase for phrase in forbidden_phrases if _normalize_text(phrase) in normalized_reply]


def _is_grounded(reply: str, sources: list[AnswerEvalSource], *, expect_no_hit: bool) -> bool:
    normalized_reply = _normalize_text(reply)
    if expect_no_hit:
        return not sources and any(marker in reply for marker in ["未命中", "信息不足", "转人工"])
    if not sources:
        return False

    joined_sources = _normalize_text("\n".join(f"{source.title}\n{source.content}" for source in sources))
    source_title_present = any(source.title and source.title in reply for source in sources)
    if not source_title_present:
        return False

    meaningful_tokens = [
        token
        for token in re.split(r"[，。；：、\s]+", reply)
        if len(_normalize_text(token)) >= 6
    ]
    if not meaningful_tokens:
        return False
    supported_tokens = sum(1 for token in meaningful_tokens if _normalize_text(token) in joined_sources)
    return supported_tokens / len(meaningful_tokens) >= 0.5 and len(normalized_reply) > 0


def build_extractive_answer(sources: list[AnswerEvalSource]) -> GeneratedAnswer:
    """Build a deterministic source-grounded answer for repeatable baseline scoring."""
    if not sources:
        return GeneratedAnswer(
            reply="当前知识库未命中与该问题直接相关的客服规则，建议补充规则后再回答或转人工确认。",
            sources=[],
            answer_source="no_hit_fallback",
        )

    primary = sources[0]
    reply = f"根据知识库《{primary.title}》：{_compact_content(primary.content)}"
    return GeneratedAnswer(reply=reply, sources=sources, answer_source="rag_extractive")


def _build_no_hit_answer() -> GeneratedAnswer:
    return GeneratedAnswer(
        reply="当前知识库未命中与该问题直接相关的客服规则，建议补充规则后再回答或转人工确认。",
        sources=[],
        answer_source="no_hit_fallback",
    )


def _build_sources(retrieved_documents) -> list[AnswerEvalSource]:
    return [
        AnswerEvalSource(
            rank=index,
            document_id=item.document_id,
            title=item.title,
            score=item.score,
            snippet=item.snippet,
            content=item.content,
        )
        for index, item in enumerate(retrieved_documents, start=1)
    ]


def _build_result(
    case: AnswerEvalCase,
    *,
    answer: GeneratedAnswer,
    latency_ms: float,
    retrieval_latency_ms: float,
    generation_latency_ms: float,
) -> AnswerEvalResult:
    source_returned = bool(answer.sources)
    source_matched = any(_source_matches_case(source, case) for source in answer.sources)
    no_hit_correct = None
    if case.expect_no_hit:
        no_hit_correct = not answer.sources

    return AnswerEvalResult(
        case=case,
        reply=answer.reply,
        answer_source=answer.answer_source,
        sources=answer.sources,
        latency_ms=latency_ms,
        retrieval_latency_ms=retrieval_latency_ms,
        generation_latency_ms=generation_latency_ms,
        source_returned=source_returned,
        source_matched=source_matched,
        keyword_coverage=_keyword_coverage(answer.reply, case.expected_keywords),
        forbidden_violations=_find_forbidden_violations(answer.reply, case.must_not_include),
        grounded=_is_grounded(answer.reply, answer.sources, expect_no_hit=case.expect_no_hit),
        no_hit_correct=no_hit_correct,
    )


def _build_summary(
    results: list[AnswerEvalResult],
    *,
    top_k: int,
    mode: str,
) -> AnswerEvalSummary:
    positive_results = [result for result in results if not result.case.expect_no_hit]
    negative_results = [result for result in results if result.case.expect_no_hit]
    positive_count = len(positive_results)
    negative_count = len(negative_results)

    source_return_rate = (
        sum(1 for result in positive_results if result.source_returned) / positive_count if positive_count else 0.0
    )
    source_match_rate = (
        sum(1 for result in positive_results if result.source_matched) / positive_count if positive_count else 0.0
    )
    keyword_cases = [result for result in positive_results if result.case.expected_keywords]
    keyword_coverage = (
        sum(result.keyword_coverage for result in keyword_cases) / len(keyword_cases) if keyword_cases else 0.0
    )
    forbidden_violation_rate = (
        sum(1 for result in results if result.forbidden_violations) / len(results) if results else 0.0
    )
    groundedness_rate = sum(1 for result in results if result.grounded) / len(results) if results else 0.0
    no_hit_accuracy = None
    if negative_count:
        no_hit_accuracy = sum(1 for result in negative_results if result.no_hit_correct is True) / negative_count
    average_latency_ms = sum(result.latency_ms for result in results) / len(results) if results else 0.0
    average_retrieval_latency_ms = (
        sum(result.retrieval_latency_ms for result in results) / len(results) if results else 0.0
    )
    average_generation_latency_ms = (
        sum(result.generation_latency_ms for result in results) / len(results) if results else 0.0
    )

    return AnswerEvalSummary(
        mode=mode,
        total_cases=len(results),
        positive_cases=positive_count,
        negative_cases=negative_count,
        top_k=top_k,
        source_return_rate=source_return_rate,
        source_match_rate=source_match_rate,
        keyword_coverage=keyword_coverage,
        forbidden_violation_rate=forbidden_violation_rate,
        groundedness_rate=groundedness_rate,
        no_hit_accuracy=no_hit_accuracy,
        average_latency_ms=average_latency_ms,
        average_retrieval_latency_ms=average_retrieval_latency_ms,
        average_generation_latency_ms=average_generation_latency_ms,
        results=results,
    )


def evaluate_answers(db: Session, cases: list[AnswerEvalCase], *, top_k: int = 3) -> AnswerEvalSummary:
    """Evaluate deterministic RAG answers against fixed answer cases."""
    from app.rag.retriever import retrieve_documents

    results: list[AnswerEvalResult] = []
    for case in cases:
        started_at = perf_counter()
        retrieval_started_at = perf_counter()
        retrieved = retrieve_documents(db, case.question, top_k=top_k)
        retrieval_latency_ms = round((perf_counter() - retrieval_started_at) * 1000, 3)
        sources = _build_sources(retrieved)
        generation_started_at = perf_counter()
        answer = build_extractive_answer(sources)
        generation_latency_ms = round((perf_counter() - generation_started_at) * 1000, 3)
        latency_ms = round((perf_counter() - started_at) * 1000, 3)

        results.append(
            _build_result(
                case,
                answer=answer,
                latency_ms=latency_ms,
                retrieval_latency_ms=retrieval_latency_ms,
                generation_latency_ms=generation_latency_ms,
            )
        )

    return _build_summary(results, top_k=top_k, mode="extractive")


async def evaluate_answers_with_llm(
    db: Session,
    cases: list[AnswerEvalCase],
    *,
    top_k: int = 3,
) -> AnswerEvalSummary:
    """Evaluate real RAG LLM answers against fixed answer cases."""
    from app.agents.orchestrator import run_chat_flow_with_context
    from app.rag.retriever import retrieve_documents

    results: list[AnswerEvalResult] = []
    for case in cases:
        started_at = perf_counter()
        retrieval_started_at = perf_counter()
        retrieved = retrieve_documents(db, case.question, top_k=top_k)
        retrieval_latency_ms = round((perf_counter() - retrieval_started_at) * 1000, 3)
        sources = _build_sources(retrieved)
        generation_started_at = perf_counter()
        if not sources:
            answer = _build_no_hit_answer()
        else:
            knowledge_context = [
                {"title": source.title, "content": source.content}
                for source in sources
            ]
            reply, _route, answer_source = await run_chat_flow_with_context(
                user_message=case.question,
                history_messages=[],
                knowledge_context=knowledge_context,
            )
            answer = GeneratedAnswer(
                reply=reply,
                sources=sources,
                answer_source=answer_source,
            )
        generation_latency_ms = round((perf_counter() - generation_started_at) * 1000, 3)
        latency_ms = round((perf_counter() - started_at) * 1000, 3)
        results.append(
            _build_result(
                case,
                answer=answer,
                latency_ms=latency_ms,
                retrieval_latency_ms=retrieval_latency_ms,
                generation_latency_ms=generation_latency_ms,
            )
        )

    return _build_summary(results, top_k=top_k, mode="llm")


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def _summary_to_payload(summary: AnswerEvalSummary) -> dict[str, Any]:
    return {
        "mode": summary.mode,
        "total_cases": summary.total_cases,
        "positive_cases": summary.positive_cases,
        "negative_cases": summary.negative_cases,
        "top_k": summary.top_k,
        "source_return_rate": summary.source_return_rate,
        "source_match_rate": summary.source_match_rate,
        "keyword_coverage": summary.keyword_coverage,
        "forbidden_violation_rate": summary.forbidden_violation_rate,
        "groundedness_rate": summary.groundedness_rate,
        "no_hit_accuracy": summary.no_hit_accuracy,
        "average_latency_ms": summary.average_latency_ms,
        "average_retrieval_latency_ms": summary.average_retrieval_latency_ms,
        "average_generation_latency_ms": summary.average_generation_latency_ms,
        "results": [
            {
                "id": result.case.case_id,
                "question": result.case.question,
                "category": result.case.category,
                "expected_source_title": result.case.expected_source_title,
                "expected_source": result.case.expected_source,
                "expect_no_hit": result.case.expect_no_hit,
                "answer_source": result.answer_source,
                "reply": result.reply,
                "source_returned": result.source_returned,
                "source_matched": result.source_matched,
                "keyword_coverage": result.keyword_coverage,
                "forbidden_violations": result.forbidden_violations,
                "grounded": result.grounded,
                "no_hit_correct": result.no_hit_correct,
                "latency_ms": result.latency_ms,
                "retrieval_latency_ms": result.retrieval_latency_ms,
                "generation_latency_ms": result.generation_latency_ms,
                "sources": [
                    {
                        "rank": source.rank,
                        "document_id": source.document_id,
                        "title": source.title,
                        "score": source.score,
                        "snippet": source.snippet,
                    }
                    for source in result.sources
                ],
            }
            for result in summary.results
        ],
    }


def write_report(summary: AnswerEvalSummary, report_path: Path) -> None:
    """Write answer evaluation results as JSON or Markdown."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.suffix.lower() == ".json":
        report_path.write_text(
            json.dumps(_summary_to_payload(summary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return

    lines = [
        "# Answer Evaluation Report",
        "",
        f"- Mode: `{summary.mode}`",
        f"- Total cases: `{summary.total_cases}`",
        f"- Positive cases: `{summary.positive_cases}`",
        f"- Negative cases: `{summary.negative_cases}`",
        f"- Top K: `{summary.top_k}`",
        f"- Source return rate: `{_format_percent(summary.source_return_rate)}`",
        f"- Source match rate: `{_format_percent(summary.source_match_rate)}`",
        f"- Keyword coverage: `{_format_percent(summary.keyword_coverage)}`",
        f"- Forbidden violation rate: `{_format_percent(summary.forbidden_violation_rate)}`",
        f"- Groundedness rate: `{_format_percent(summary.groundedness_rate)}`",
        f"- Negative no-hit accuracy: `{_format_percent(summary.no_hit_accuracy)}`",
        f"- Average latency: `{summary.average_latency_ms:.3f} ms`",
        f"- Average retrieval latency: `{summary.average_retrieval_latency_ms:.3f} ms`",
        f"- Average generation latency: `{summary.average_generation_latency_ms:.3f} ms`",
        "",
        "| Case ID | Question | Expected | Top Source | Source Match | Keyword Coverage | Grounded | Retrieval | Generation | Total |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in summary.results:
        expected = "NO_HIT" if result.case.expect_no_hit else (
            result.case.expected_source_title or result.case.expected_source or ""
        )
        top_source = result.sources[0].title if result.sources else "NO_HIT"
        forbidden = ", ".join(result.forbidden_violations)
        lines.append(
            f"| `{result.case.case_id}` | {result.case.question} | {expected} | {top_source} | "
            f"{result.source_matched} | {result.keyword_coverage:.2f} | {result.grounded} | "
            f"{result.retrieval_latency_ms:.3f} ms | {result.generation_latency_ms:.3f} ms | "
            f"{result.latency_ms:.3f} ms |"
        )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _seed_database_from_vector_metadata(db: Session) -> int:
    from app.models.knowledge_document import KnowledgeDocument
    from app.rag.vector_store import FAISS_METADATA_PATH

    if not FAISS_METADATA_PATH.exists():
        return 0

    metadata = json.loads(FAISS_METADATA_PATH.read_text(encoding="utf-8"))
    for item in metadata:
        db.add(
            KnowledgeDocument(
                document_id=item["document_id"],
                title=item["title"],
                source_type=item.get("source_type", "text"),
                source_path=item.get("source_path"),
                content=item["content"],
                status="indexed",
            )
        )
    db.commit()
    return len(metadata)


def _create_metadata_seed_session() -> tuple[Session, Any]:
    from app.db.base import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    db = SessionLocal()
    _seed_database_from_vector_metadata(db)
    return db, engine


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate ServiceMind answer quality.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--mode",
        choices=["extractive", "llm"],
        default="extractive",
        help="extractive uses deterministic source text; llm calls the configured chat model with RAG context.",
    )
    parser.add_argument(
        "--source",
        choices=["metadata", "database"],
        default="metadata",
        help="metadata seeds a temporary DB from current vector metadata; database uses app DB settings.",
    )
    return parser.parse_args()


def main() -> int:
    """Run answer evaluation from the command line."""
    args = _parse_args()
    cases = load_cases(args.dataset)

    if args.source == "metadata":
        db, engine = _create_metadata_seed_session()
        try:
            if args.mode == "llm":
                summary = asyncio.run(evaluate_answers_with_llm(db, cases, top_k=args.top_k))
            else:
                summary = evaluate_answers(db, cases, top_k=args.top_k)
        finally:
            db.close()
            engine.dispose()
    else:
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            if args.mode == "llm":
                summary = asyncio.run(evaluate_answers_with_llm(db, cases, top_k=args.top_k))
            else:
                summary = evaluate_answers(db, cases, top_k=args.top_k)

    write_report(summary, args.report)
    print(
        "Answer eval finished: "
        f"mode={summary.mode}, cases={summary.total_cases}, "
        f"positives={summary.positive_cases}, negatives={summary.negative_cases}, "
        f"source_return={_format_percent(summary.source_return_rate)}, "
        f"source_match={_format_percent(summary.source_match_rate)}, "
        f"keyword_coverage={_format_percent(summary.keyword_coverage)}, "
        f"groundedness={_format_percent(summary.groundedness_rate)}, "
        f"no_hit_accuracy={_format_percent(summary.no_hit_accuracy)}, "
        f"retrieval_ms={summary.average_retrieval_latency_ms:.3f}, "
        f"generation_ms={summary.average_generation_latency_ms:.3f}, "
        f"report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
