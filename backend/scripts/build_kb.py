"""Offline knowledge base build pipeline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys
from time import perf_counter

from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "reports"
DEFAULT_REPORT_PATH = DEFAULT_REPORT_DIR / "kb_build_report.md"


@dataclass(slots=True)
class BuildFileResult:
    """Per-file processing result for the offline build report."""

    path: str
    status: str
    source_type: str | None = None
    chunk_count: int = 0
    error: str | None = None


@dataclass(slots=True)
class BuildIndexReport:
    """Summary of one offline index build run."""

    source_dir: str
    supported_suffixes: list[str]
    files_seen: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    indexed_count: int = 0
    vector_count: int = 0
    duration_seconds: float = 0.0
    file_results: list[BuildFileResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return whether this run completed without file-level failures."""
        return self.files_failed == 0


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _iter_source_files(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        raise FileNotFoundError(f"source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"source path is not a directory: {source_dir}")
    return sorted(path for path in source_dir.rglob("*") if path.is_file())


def _write_json_report(report: BuildIndexReport, report_path: Path) -> None:
    payload = {
        "success": report.success,
        "source_dir": report.source_dir,
        "supported_suffixes": report.supported_suffixes,
        "files_seen": report.files_seen,
        "files_processed": report.files_processed,
        "files_skipped": report.files_skipped,
        "files_failed": report.files_failed,
        "indexed_count": report.indexed_count,
        "vector_count": report.vector_count,
        "duration_seconds": report.duration_seconds,
        "file_results": [
            {
                "path": item.path,
                "status": item.status,
                "source_type": item.source_type,
                "chunk_count": item.chunk_count,
                "error": item.error,
            }
            for item in report.file_results
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown_report(report: BuildIndexReport, report_path: Path) -> None:
    lines = [
        "# Knowledge Base Build Report",
        "",
        f"- Source directory: `{report.source_dir}`",
        f"- Success: `{report.success}`",
        f"- Files seen: `{report.files_seen}`",
        f"- Files processed: `{report.files_processed}`",
        f"- Files skipped: `{report.files_skipped}`",
        f"- Files failed: `{report.files_failed}`",
        f"- Indexed chunks: `{report.indexed_count}`",
        f"- Vector count: `{report.vector_count}`",
        f"- Duration seconds: `{report.duration_seconds:.3f}`",
        "",
        "| File | Status | Source Type | Chunks | Error |",
        "|---|---|---|---:|---|",
    ]
    for item in report.file_results:
        error = item.error or ""
        source_type = item.source_type or ""
        lines.append(f"| `{item.path}` | {item.status} | {source_type} | {item.chunk_count} | {error} |")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(report: BuildIndexReport, report_path: Path) -> None:
    """Write a build report as JSON or Markdown based on the file suffix."""
    if report_path.suffix.lower() == ".json":
        _write_json_report(report, report_path)
    else:
        _write_markdown_report(report, report_path)


def build_knowledge_index(db: Session, *, source_dir: Path) -> BuildIndexReport:
    """Build the knowledge index from local files and return a detailed report."""
    from app.repositories.kb_repository import KnowledgeBaseRepository
    from app.rag.ingestion import SUPPORTED_SOURCE_SUFFIXES, build_chunked_documents, clean_text
    from app.rag.vector_store import rebuild_vector_store

    started_at = perf_counter()
    source_dir = source_dir.resolve()
    files = _iter_source_files(source_dir)

    report = BuildIndexReport(
        source_dir=str(source_dir),
        supported_suffixes=sorted(SUPPORTED_SOURCE_SUFFIXES),
        files_seen=len(files),
    )
    repository = KnowledgeBaseRepository(db)
    repository.delete_all()

    indexed_documents = []
    for path in files:
        suffix = path.suffix.lower()
        relative_path = _relative_path(path)
        if suffix not in SUPPORTED_SOURCE_SUFFIXES:
            report.files_skipped += 1
            report.file_results.append(
                BuildFileResult(
                    path=relative_path,
                    status="skipped",
                    error=f"unsupported suffix: {suffix or '<none>'}",
                )
            )
            continue

        try:
            raw_content = path.read_text(encoding="utf-8")
            cleaned_content = clean_text(raw_content)
            if not cleaned_content:
                report.files_skipped += 1
                report.file_results.append(
                    BuildFileResult(
                        path=relative_path,
                        status="skipped",
                        source_type=suffix.lstrip("."),
                        error="empty after cleaning",
                    )
                )
                continue

            chunked_documents = build_chunked_documents(
                title=path.stem,
                content=cleaned_content,
                source_type=suffix.lstrip("."),
                source_path=str(path),
            )
            created_count = 0
            for document in chunked_documents:
                indexed_documents.append(
                    repository.create(
                        title=document["title"],
                        content=document["content"],
                        source_type=document["source_type"],
                        source_path=document.get("source_path"),
                    )
                )
                created_count += 1

            report.files_processed += 1
            report.indexed_count += created_count
            report.file_results.append(
                BuildFileResult(
                    path=relative_path,
                    status="indexed",
                    source_type=suffix.lstrip("."),
                    chunk_count=created_count,
                )
            )
        except Exception as exc:
            db.rollback()
            report.files_failed += 1
            report.file_results.append(
                BuildFileResult(
                    path=relative_path,
                    status="failed",
                    source_type=suffix.lstrip("."),
                    error=str(exc),
                )
            )

    report.vector_count = rebuild_vector_store(repository.list_indexed_documents())
    report.duration_seconds = round(perf_counter() - started_at, 3)
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the ServiceMind offline knowledge index.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing raw knowledge files. Supported: .txt, .md",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Report output path. Use .json for JSON, otherwise Markdown.",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Optional SQLAlchemy database URL for this run. Overrides DATABASE_URL before DB setup.",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Create database tables before building the index.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the offline build pipeline from the command line."""
    args = _parse_args()
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    from app.db.session import SessionLocal, init_db

    if args.init_db:
        init_db()

    with SessionLocal() as db:
        report = build_knowledge_index(db, source_dir=args.input)
    write_report(report, args.report)

    print(
        "KB build finished: "
        f"processed={report.files_processed}, skipped={report.files_skipped}, "
        f"failed={report.files_failed}, indexed={report.indexed_count}, "
        f"vectors={report.vector_count}, report={args.report}"
    )
    return 0 if report.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
