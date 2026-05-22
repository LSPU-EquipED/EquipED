"""Retrieval interface for querying context from Chroma collections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from server.core.chroma import get_chroma_client
from server.core.embedding import get_embedding_model


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Normalized retrieval result consumed by downstream evaluators."""

    text: str
    distance: float
    document_id: str | None
    source_type: str | None
    page_number: int | None
    is_ocr: bool | None
    token_count: int | None


def retrieve_context(
    query_text: str,
    collection_name: str,
    n_results: int = 5,
    document_id_filter: str | None = None,
) -> list[RetrievedChunk]:
    """Retrieve nearest chunks from a Chroma collection."""

    if not query_text.strip():
        return []

    try:
        model = get_embedding_model()
        query_embedding = model.encode([query_text], show_progress_bar=False).tolist()[0]

        collection = get_chroma_client().get_collection(collection_name)

        where_filter: dict[str, Any] | None = None
        if document_id_filter:
            where_filter = {"document_id": {"$eq": document_id_filter}}

        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        return _parse_chroma_results(result)
    except Exception:
        return []


def _parse_chroma_results(result: dict[str, Any]) -> list[RetrievedChunk]:
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    parsed: list[RetrievedChunk] = []
    for index, text in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else 0.0
        metadata = metadata or {}
        parsed.append(
            RetrievedChunk(
                text=str(text),
                distance=float(distance),
                document_id=metadata.get("document_id"),
                source_type=metadata.get("source_type"),
                page_number=metadata.get("page_number"),
                is_ocr=metadata.get("is_ocr"),
                token_count=metadata.get("token_count"),
            )
        )
    return parsed


__all__ = ["RetrievedChunk", "retrieve_context"]
