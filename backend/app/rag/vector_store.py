"""Vector store integration module."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np

from app.rag.embeddings import embed_documents, embed_text


PROJECT_ROOT = Path(__file__).resolve().parents[3]
VECTOR_STORE_ROOT = PROJECT_ROOT / "data" / "vector_store"
FAISS_INDEX_PATH = VECTOR_STORE_ROOT / "servicemind.faiss"
FAISS_METADATA_PATH = VECTOR_STORE_ROOT / "metadata.json"


@dataclass(slots=True)
class VectorSearchHit:
    """Single vector search hit loaded from FAISS metadata."""

    document_id: str
    title: str
    source_type: str
    source_path: str | None
    score: float
    snippet: str
    content: str


def _import_faiss():
    try:
        import faiss  # type: ignore

        return faiss
    except Exception:
        return None


def _to_float32_matrix(vectors: list[list[float]]) -> np.ndarray:
    matrix = np.array(vectors, dtype="float32")
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _load_metadata() -> list[dict[str, Any]]:
    if not FAISS_METADATA_PATH.exists():
        return []
    return json.loads(FAISS_METADATA_PATH.read_text(encoding="utf-8"))


def rebuild_vector_store(documents: list[Any]) -> int:
    """Rebuild the local FAISS index from indexed knowledge documents."""
    faiss = _import_faiss()
    if faiss is None:
        return 0

    VECTOR_STORE_ROOT.mkdir(parents=True, exist_ok=True)
    indexed_documents = [document for document in documents if getattr(document, "content", "").strip()]
    if not indexed_documents:
        if FAISS_INDEX_PATH.exists():
            FAISS_INDEX_PATH.unlink()
        FAISS_METADATA_PATH.write_text("[]", encoding="utf-8")
        return 0

    embeddings = embed_documents([document.content for document in indexed_documents])
    matrix = _to_float32_matrix(embeddings)
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    faiss.write_index(index, str(FAISS_INDEX_PATH))

    metadata = [
        {
            "document_id": document.document_id,
            "title": document.title,
            "source_type": document.source_type,
            "source_path": document.source_path,
            "content": document.content,
        }
        for document in indexed_documents
    ]
    FAISS_METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(metadata)


def search_vector_store(query: str, *, top_k: int = 3) -> list[VectorSearchHit]:
    """Search the local FAISS index and return matching metadata records."""
    faiss = _import_faiss()
    if faiss is None or not FAISS_INDEX_PATH.exists():
        return []

    metadata = _load_metadata()
    if not metadata:
        return []

    index = faiss.read_index(str(FAISS_INDEX_PATH))
    query_vector = _to_float32_matrix([embed_text(query)])
    scores, indices = index.search(query_vector, min(top_k, len(metadata)))

    hits: list[VectorSearchHit] = []
    for score, index_value in zip(scores[0].tolist(), indices[0].tolist(), strict=False):
        if index_value < 0 or index_value >= len(metadata):
            continue
        item = metadata[index_value]
        content = item["content"]
        hits.append(
            VectorSearchHit(
                document_id=item["document_id"],
                title=item["title"],
                source_type=item["source_type"],
                source_path=item.get("source_path"),
                score=float(score),
                snippet=content[:160].strip(),
                content=content,
            )
        )
    return hits
