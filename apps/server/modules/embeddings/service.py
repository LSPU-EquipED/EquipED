"""Embedding and Chroma upsert service for Layer 2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chromadb.errors import NotFoundError
from server.core.chroma import get_chroma_client
from server.core.embedding import get_embedding_model

from .collections import COL_SLM_ALL, COL_SLM_PREFIX, resolve_collection_name


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
    policy_area: str | None = None
    section_ref: str | None = None
    chunk_index: int | None = None


def _omit_none(d: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with all keys whose value is None omitted."""
    return {k: v for k, v in d.items() if v is not None}


def _to_embedding_chunk(chunk: Any) -> EmbeddingChunk:
    return EmbeddingChunk(
        chunk_id=str(chunk.chunk_id),
        document_id=str(chunk.document_id),
        source_type=str(chunk.source_type),
        page_number=getattr(chunk, "page_number", None),
        text=str(chunk.text),
        token_count=getattr(chunk, "token_count", None),
        is_ocr=bool(getattr(chunk, "is_ocr", False)),
        policy_area=getattr(chunk, "policy_area", None),
        section_ref=getattr(chunk, "section_ref", None),
        chunk_index=getattr(chunk, "chunk_index", None),
    )


def embed_and_store_chunks(chunks: list[Any], batch_size: int = 32) -> int:
    """Embed chunks and upsert them into target Chroma collections.

    Returns number of chunks successfully sent for upsert.
    """

    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    normalized = [
        _to_embedding_chunk(chunk) for chunk in chunks if getattr(chunk, "text", None)
    ]
    if not normalized:
        return 0

    grouped: dict[str, list[EmbeddingChunk]] = {}
    for chunk in normalized:
        if chunk.source_type == "slm":
            raise ValueError("SLM chunks must be indexed through build_slm_retrieval")
        collection_name = resolve_collection_name(chunk.source_type)
        grouped.setdefault(collection_name, []).append(chunk)

    model = get_embedding_model()
    chroma_client = get_chroma_client()
    client_max_batch = getattr(chroma_client, "get_max_batch_size", None)
    effective_batch_size = min(
        batch_size,
        client_max_batch() if callable(client_max_batch) else batch_size,
    )

    upserted = 0
    for collection_name, grouped_chunks in grouped.items():
        collection = chroma_client.get_or_create_collection(
            collection_name, embedding_function=None
        )

        for start in range(0, len(grouped_chunks), effective_batch_size):
            batch = grouped_chunks[start : start + effective_batch_size]
            texts = [chunk.text for chunk in batch]
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
            ).tolist()
            ids = [chunk.chunk_id for chunk in batch]
            metadatas = [
                _omit_none(
                    {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "source_type": chunk.source_type,
                        "page_number": chunk.page_number,
                        "is_ocr": chunk.is_ocr,
                        "token_count": chunk.token_count,
                        "policy_area": chunk.policy_area,
                        "section_ref": chunk.section_ref,
                        "chunk_index": chunk.chunk_index,
                    }
                )
                for chunk in batch
            ]

            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            upserted += len(batch)

    return upserted


def delete_chroma_vectors(document_id: str, source_type: str) -> bool:
    """Delete all Chroma vectors for a given document_id and source_type.

    Returns True if the collection exists and deletion was attempted,
    False if the collection does not exist.
    """
    try:
        resolve_collection_name(source_type)
    except ValueError:
        return False

    return delete_chroma_vectors_strict(document_id, source_type)


def delete_chroma_vectors_strict(document_id: str, source_type: str) -> bool:
    """Strictly delete all Chroma vectors for document_id and source_type.

    - Resolves target collection name; raises ValueError if unsupported source_type.
    - Connects to Chroma; raises if Chroma connection fails.
    - Treats ONLY an explicitly missing collection as benign (returns False).
    - Propagates all connection/get/query/delete errors.
    - Deletes scoped vectors and verifies zero remain.
    """
    chroma_client = get_chroma_client()

    if source_type == "slm":
        collection_names = _slm_collection_names(chroma_client)
        deleted_any = False
        for collection_name in collection_names:
            try:
                collection = chroma_client.get_collection(collection_name)
            except NotFoundError:
                continue
            collection.delete(where={"document_id": {"$eq": document_id}})
            remaining = collection.get(
                where={"document_id": {"$eq": document_id}}, limit=1
            )
            if remaining.get("ids"):
                raise RuntimeError(
                    f"Chroma vectors remain for document {document_id} in "
                    f"{collection_name} after deletion."
                )
            deleted_any = True
        return deleted_any

    collection_name = resolve_collection_name(source_type)

    try:
        collection = chroma_client.get_collection(collection_name)
    except NotFoundError:
        return False

    collection.delete(where={"document_id": {"$eq": document_id}})

    remaining = collection.get(
        where={"document_id": {"$eq": document_id}},
        limit=1,
    )
    if remaining.get("ids") and len(remaining["ids"]) > 0:
        raise RuntimeError(
            f"Chroma vectors remain for document {document_id} in {collection_name} "
            "after deletion."
        )

    return True


def check_chroma_availability(document_id: str, source_type: str) -> bool:
    """Return True if at least one vector exists for the given document in Chroma."""
    try:
        collection_name = (
            None if source_type == "slm" else resolve_collection_name(source_type)
        )
    except ValueError:
        return False

    try:
        chroma_client = get_chroma_client()
        if source_type == "slm":
            for slm_collection_name in _slm_collection_names(chroma_client):
                collection = chroma_client.get_collection(slm_collection_name)
                result = collection.get(
                    where={"document_id": {"$eq": document_id}}, limit=1
                )
                if result.get("ids"):
                    return True
            return False
        collection = chroma_client.get_collection(collection_name)
    except Exception:
        return False

    try:
        result = collection.get(
            where={"document_id": {"$eq": document_id}},
            limit=1,
        )
        return len(result.get("ids", [])) > 0
    except Exception:
        return False


def _slm_collection_names(chroma_client: Any) -> list[str]:
    """List only the reserved legacy and model/dimension-specific SLM collections."""
    names = []
    for item in chroma_client.list_collections():
        name = item if isinstance(item, str) else getattr(item, "name", None)
        if name == COL_SLM_ALL or (
            isinstance(name, str) and name.startswith(COL_SLM_PREFIX)
        ):
            names.append(name)
    return names


__all__ = [
    "EmbeddingChunk",
    "embed_and_store_chunks",
    "delete_chroma_vectors",
    "delete_chroma_vectors_strict",
    "check_chroma_availability",
]
