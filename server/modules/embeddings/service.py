"""Embedding and Chroma upsert service for Layer 2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from server.core.chroma import get_chroma_client
from server.core.embedding import get_embedding_model

from .collections import resolve_collection_name


@dataclass(frozen=True, slots=True)
class EmbeddingChunk:
    """Minimal contract required to embed and persist a chunk."""

    chunk_id: str
    document_id: str
    source_type: str
    page_number: int | None
    text: str
    token_count: int | None
    is_ocr: bool


def _to_embedding_chunk(chunk: Any) -> EmbeddingChunk:
    return EmbeddingChunk(
        chunk_id=str(chunk.chunk_id),
        document_id=str(chunk.document_id),
        source_type=str(chunk.source_type),
        page_number=getattr(chunk, "page_number", None),
        text=str(chunk.text),
        token_count=getattr(chunk, "token_count", None),
        is_ocr=bool(getattr(chunk, "is_ocr", False)),
    )


def embed_and_store_chunks(chunks: list[Any], batch_size: int = 32) -> int:
    """Embed chunks and upsert them into target Chroma collections.

    Returns number of chunks successfully sent for upsert.
    """

    normalized = [
        _to_embedding_chunk(chunk)
        for chunk in chunks
        if getattr(chunk, "text", None)
    ]
    if not normalized:
        return 0

    grouped: dict[str, list[EmbeddingChunk]] = {}
    for chunk in normalized:
        collection_name = resolve_collection_name(chunk.source_type)
        grouped.setdefault(collection_name, []).append(chunk)

    model = get_embedding_model()
    chroma_client = get_chroma_client()

    upserted = 0
    for collection_name, grouped_chunks in grouped.items():
        collection = chroma_client.get_or_create_collection(collection_name)

        texts = [chunk.text for chunk in grouped_chunks]
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
        ).tolist()
        ids = [chunk.chunk_id for chunk in grouped_chunks]
        metadatas = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "source_type": chunk.source_type,
                "page_number": chunk.page_number,
                "is_ocr": chunk.is_ocr,
                "token_count": chunk.token_count,
            }
            for chunk in grouped_chunks
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        upserted += len(grouped_chunks)

    return upserted


def embed_document_chunks(chunks: list[Any], batch_size: int = 32) -> int:
    """Compatibility wrapper for document-layer callers."""

    return embed_and_store_chunks(chunks, batch_size=batch_size)


__all__ = ["EmbeddingChunk", "embed_and_store_chunks", "embed_document_chunks"]
