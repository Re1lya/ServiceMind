"""Run one local RAG chat turn from the command line."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


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
    parser = argparse.ArgumentParser(description="Run one ServiceMind RAG chat query against the configured LLM.")
    parser.add_argument("question", help="User question to answer with RAG.")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--source",
        choices=["metadata", "database"],
        default="metadata",
        help="metadata seeds a temporary DB from current vector metadata; database uses app DB settings.",
    )
    return parser.parse_args()


async def _run_once(db: Session, *, question: str, top_k: int) -> None:
    from app.agents.orchestrator import run_chat_flow_with_context
    from app.core.config import settings
    from app.rag.retriever import retrieve_documents

    retrieved_documents = retrieve_documents(db, question, top_k=top_k)
    knowledge_context = [
        {"title": item.title, "content": item.content}
        for item in retrieved_documents
    ]
    reply, route, answer_source = await run_chat_flow_with_context(
        user_message=question,
        history_messages=[],
        knowledge_context=knowledge_context,
    )

    print(f"LLM: {settings.llm_model_name} @ {settings.resolved_llm_api_base}")
    print(f"Route: {route}")
    print(f"Answer source: {answer_source}")
    print("Sources:")
    if retrieved_documents:
        for index, document in enumerate(retrieved_documents, start=1):
            print(f"  {index}. {document.title} score={document.score:.4f}")
    else:
        print("  NO_HIT")
    print("\nReply:")
    print(reply)


def main() -> int:
    """Run one local RAG chat turn."""
    args = _parse_args()

    if args.source == "metadata":
        db, engine = _create_metadata_seed_session()
        try:
            asyncio.run(_run_once(db, question=args.question, top_k=args.top_k))
        finally:
            db.close()
            engine.dispose()
    else:
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            asyncio.run(_run_once(db, question=args.question, top_k=args.top_k))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
