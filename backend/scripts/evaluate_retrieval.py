"""Offline retrieval evaluation script."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEFAULT_DATASET_PATH = PROJECT_ROOT / "data" / "eval" / "retrieval_questions.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "reports" / "retrieval_eval_report.md"


@dataclass(slots=True)
class RetrievalEvalCase:
    """Single retrieval evaluation case."""

    case_id: str
    question: str
    category: str = "general"
    gold_doc_id: str | None = None
    gold_title: str | None = None
    expected_keywords: list[str] = field(default_factory=list)
    expect_no_hit: bool = False


@dataclass(slots=True)
class RetrievalEvalHit:
    """Single retrieved hit serialized for reports."""

    rank: int
    document_id: str
    title: str
    score: float
    snippet: str


@dataclass(slots=True)
class RetrievalEvalResult:
    """Per-case evaluation result."""

    case: RetrievalEvalCase
    hits: list[RetrievalEvalHit]
    latency_ms: float
    hit_rank: int | None
    is_hit_at_1: bool
    is_recall_at_k: bool
    is_no_hit_correct: bool | None
    keyword_coverage: float


@dataclass(slots=True)
class RetrievalEvalSummary:
    """Aggregate retrieval evaluation metrics."""

    total_cases: int
    positive_cases: int
    negative_cases: int
    top_k: int
    hit_at_1: float
    recall_at_k: float
    mrr: float
    no_hit_accuracy: float | None
    keyword_coverage: float
    average_latency_ms: float
    results: list[RetrievalEvalResult]


def load_cases(dataset_path: Path) -> list[RetrievalEvalCase]:
    """Load retrieval evaluation cases from JSON."""
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases: list[RetrievalEvalCase] = []
    for item in payload:
        cases.append(
            RetrievalEvalCase(
                case_id=item["id"],
                question=item["question"],
                category=item.get("category", "general"),
                gold_doc_id=item.get("gold_doc_id"),
                gold_title=item.get("gold_title"),
                expected_keywords=list(item.get("expected_keywords") or []),
                expect_no_hit=bool(item.get("expect_no_hit", False)),
            )
        )
    return cases


def _hit_matches_case(hit: RetrievalEvalHit, case: RetrievalEvalCase) -> bool:
    if case.gold_doc_id and hit.document_id == case.gold_doc_id:
        return True
    if case.gold_title and hit.title == case.gold_title:
        return True
    return False


def _keyword_coverage(hits: list[RetrievalEvalHit], expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 0.0
    joined_text = "\n".join(f"{hit.title}\n{hit.snippet}" for hit in hits)
    matched_count = sum(1 for keyword in expected_keywords if keyword in joined_text)
    return matched_count / len(expected_keywords)


def evaluate_retrieval(db: Session, cases: list[RetrievalEvalCase], *, top_k: int = 5) -> RetrievalEvalSummary:
    """Evaluate current RAG retrieval behavior against fixed cases."""
    from app.rag.retriever import retrieve_documents

    results: list[RetrievalEvalResult] = []
    for case in cases:
        started_at = perf_counter()
        retrieved = retrieve_documents(db, case.question, top_k=top_k)
        latency_ms = round((perf_counter() - started_at) * 1000, 3)
        hits = [
            RetrievalEvalHit(
                rank=index,
                document_id=item.document_id,
                title=item.title,
                score=item.score,
                snippet=item.snippet,
            )
            for index, item in enumerate(retrieved, start=1)
        ]

        hit_rank = None
        for hit in hits:
            if _hit_matches_case(hit, case):
                hit_rank = hit.rank
                break

        is_no_hit_correct = None
        if case.expect_no_hit:
            is_no_hit_correct = len(hits) == 0

        results.append(
            RetrievalEvalResult(
                case=case,
                hits=hits,
                latency_ms=latency_ms,
                hit_rank=hit_rank,
                is_hit_at_1=hit_rank == 1,
                is_recall_at_k=hit_rank is not None and hit_rank <= top_k,
                is_no_hit_correct=is_no_hit_correct,
                keyword_coverage=_keyword_coverage(hits, case.expected_keywords),
            )
        )

    positive_results = [result for result in results if not result.case.expect_no_hit]
    negative_results = [result for result in results if result.case.expect_no_hit]
    positive_count = len(positive_results)
    negative_count = len(negative_results)

    hit_at_1 = sum(1 for result in positive_results if result.is_hit_at_1) / positive_count if positive_count else 0.0
    recall_at_k = (
        sum(1 for result in positive_results if result.is_recall_at_k) / positive_count if positive_count else 0.0
    )
    mrr = (
        sum((1 / result.hit_rank) for result in positive_results if result.hit_rank is not None) / positive_count
        if positive_count
        else 0.0
    )
    no_hit_accuracy = None
    if negative_count:
        no_hit_accuracy = (
            sum(1 for result in negative_results if result.is_no_hit_correct is True) / negative_count
        )
    keyword_cases = [result for result in positive_results if result.case.expected_keywords]
    keyword_coverage = (
        sum(result.keyword_coverage for result in keyword_cases) / len(keyword_cases) if keyword_cases else 0.0
    )
    average_latency_ms = sum(result.latency_ms for result in results) / len(results) if results else 0.0

    return RetrievalEvalSummary(
        total_cases=len(results),
        positive_cases=positive_count,
        negative_cases=negative_count,
        top_k=top_k,
        hit_at_1=hit_at_1,
        recall_at_k=recall_at_k,
        mrr=mrr,
        no_hit_accuracy=no_hit_accuracy,
        keyword_coverage=keyword_coverage,
        average_latency_ms=average_latency_ms,
        results=results,
    )


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def _summary_to_payload(summary: RetrievalEvalSummary) -> dict[str, Any]:
    return {
        "total_cases": summary.total_cases,
        "positive_cases": summary.positive_cases,
        "negative_cases": summary.negative_cases,
        "top_k": summary.top_k,
        "hit_at_1": summary.hit_at_1,
        "recall_at_k": summary.recall_at_k,
        "mrr": summary.mrr,
        "no_hit_accuracy": summary.no_hit_accuracy,
        "keyword_coverage": summary.keyword_coverage,
        "average_latency_ms": summary.average_latency_ms,
        "results": [
            {
                "id": result.case.case_id,
                "question": result.case.question,
                "category": result.case.category,
                "gold_doc_id": result.case.gold_doc_id,
                "gold_title": result.case.gold_title,
                "expect_no_hit": result.case.expect_no_hit,
                "hit_rank": result.hit_rank,
                "hit_at_1": result.is_hit_at_1,
                "recall_at_k": result.is_recall_at_k,
                "no_hit_correct": result.is_no_hit_correct,
                "keyword_coverage": result.keyword_coverage,
                "latency_ms": result.latency_ms,
                "hits": [
                    {
                        "rank": hit.rank,
                        "document_id": hit.document_id,
                        "title": hit.title,
                        "score": hit.score,
                        "snippet": hit.snippet,
                    }
                    for hit in result.hits
                ],
            }
            for result in summary.results
        ],
    }


def write_report(summary: RetrievalEvalSummary, report_path: Path) -> None:
    """Write evaluation results as JSON or Markdown."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.suffix.lower() == ".json":
        report_path.write_text(
            json.dumps(_summary_to_payload(summary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return

    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- Total cases: `{summary.total_cases}`",
        f"- Positive cases: `{summary.positive_cases}`",
        f"- Negative cases: `{summary.negative_cases}`",
        f"- Top K: `{summary.top_k}`",
        f"- Hit@1: `{_format_percent(summary.hit_at_1)}`",
        f"- Recall@{summary.top_k}: `{_format_percent(summary.recall_at_k)}`",
        f"- MRR: `{summary.mrr:.4f}`",
        f"- Negative no-hit accuracy: `{_format_percent(summary.no_hit_accuracy)}`",
        f"- Keyword coverage: `{_format_percent(summary.keyword_coverage)}`",
        f"- Average latency: `{summary.average_latency_ms:.3f} ms`",
        "",
        "| Case ID | Question | Expected | Top1 | Hit Rank | Keyword Coverage | Latency |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for result in summary.results:
        expected = "NO_HIT" if result.case.expect_no_hit else (result.case.gold_title or result.case.gold_doc_id or "")
        top1 = result.hits[0].title if result.hits else "NO_HIT"
        hit_rank = result.hit_rank if result.hit_rank is not None else ""
        lines.append(
            f"| `{result.case.case_id}` | {result.case.question} | {expected} | {top1} | "
            f"{hit_rank} | {result.keyword_coverage:.2f} | {result.latency_ms:.3f} ms |"
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
    parser = argparse.ArgumentParser(description="Evaluate ServiceMind retrieval quality.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--source",
        choices=["metadata", "database"],
        default="metadata",
        help="metadata seeds a temporary DB from current vector metadata; database uses app DB settings.",
    )
    return parser.parse_args()


def main() -> int:
    """Run retrieval evaluation from the command line."""
    args = _parse_args()
    cases = load_cases(args.dataset)

    if args.source == "metadata":
        db, engine = _create_metadata_seed_session()
        try:
            summary = evaluate_retrieval(db, cases, top_k=args.top_k)
        finally:
            db.close()
            engine.dispose()
    else:
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            summary = evaluate_retrieval(db, cases, top_k=args.top_k)

    write_report(summary, args.report)
    print(
        "Retrieval eval finished: "
        f"cases={summary.total_cases}, positives={summary.positive_cases}, negatives={summary.negative_cases}, "
        f"hit@1={_format_percent(summary.hit_at_1)}, recall@{summary.top_k}={_format_percent(summary.recall_at_k)}, "
        f"mrr={summary.mrr:.4f}, no_hit_accuracy={_format_percent(summary.no_hit_accuracy)}, "
        f"report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
