"""Knowledge ingestion pipeline module."""

from __future__ import annotations

from pathlib import Path


SUPPORTED_SOURCE_SUFFIXES = {".txt", ".md"}
DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 80


def clean_text(content: str) -> str:
    """Normalize whitespace for MVP knowledge ingestion."""
    lines = [line.strip() for line in content.replace("\r\n", "\n").split("\n")]
    filtered = [line for line in lines if line]
    return "\n".join(filtered).strip()


def split_text_chunks(
    content: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split cleaned text into retrieval-sized chunks with small overlap."""
    cleaned = clean_text(content)
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        if end < len(cleaned):
            boundary_candidates = [
                cleaned.rfind("\n", start, end),
                cleaned.rfind("。", start, end),
                cleaned.rfind("；", start, end),
                cleaned.rfind(".", start, end),
            ]
            boundary = max(boundary_candidates)
            if boundary > start + chunk_size // 2:
                end = boundary + 1

        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(0, end - chunk_overlap)
    return chunks


def build_chunked_documents(
    *,
    title: str,
    content: str,
    source_type: str,
    source_path: str | None,
) -> list[dict[str, str]]:
    """Convert a source document into one or more indexed chunk records."""
    chunks = split_text_chunks(content)
    documents: list[dict[str, str]] = []
    for index, chunk in enumerate(chunks, start=1):
        chunk_title = title if len(chunks) == 1 else f"{title} / 片段 {index}"
        document: dict[str, str] = {
            "title": chunk_title,
            "content": chunk,
            "source_type": source_type,
        }
        if source_path:
            document["source_path"] = source_path
        documents.append(document)
    return documents


def load_documents(source_dir: Path) -> list[dict[str, str]]:
    """Load plain text knowledge documents from the configured source directory."""
    if not source_dir.exists():
        return []

    documents: list[dict[str, str]] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES:
            continue
        raw_content = path.read_text(encoding="utf-8")
        cleaned_content = clean_text(raw_content)
        if not cleaned_content:
            continue
        documents.extend(
            build_chunked_documents(
                title=path.stem,
                content=cleaned_content,
                source_type=path.suffix.lower().lstrip("."),
                source_path=str(path),
            )
        )
    return documents
