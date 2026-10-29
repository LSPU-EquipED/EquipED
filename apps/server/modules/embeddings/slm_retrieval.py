"""Document-scoped semantic indexing for direct SLM evaluation inputs."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from numbers import Real
from typing import Any
from uuid import UUID

from equiped_harness.runtime.source_retrieval import (
    SLM_SOURCE_SPAN_CHARS,
    source_hash,
)
from server.core.chroma import get_chroma_client
from server.core.config import get_settings
from server.core.embedding import get_embedding_model

from .collections import resolve_slm_collection_name

_CHUNK_CHARS = 800
_CHUNKING_VERSION = "slm-subchunk-v1"
_RESULT_LIMIT = 12
_READ_PAGE_SIZE = 128


def _parts(text: str, model: Any) -> list[tuple[int, int, str]]:
    """Split source spans at character bounds and respect tokenizer limits."""
    max_chars = _CHUNK_CHARS
    tokenizer = getattr(model, "tokenizer", None)
    max_seq_length = getattr(model, "max_seq_length", None)
    if tokenizer is not None and isinstance(max_seq_length, int) and max_seq_length > 8:
        # Character slicing remains the bound; tokenizer checks shrink it when needed.
        probe = text[:max_chars]
        try:
            while (
                len(probe) > 1
                and len(
                    tokenizer.encode(
                        probe, add_special_tokens=True, truncation=False, verbose=False
                    )
                )
                > max_seq_length
            ):
                max_chars = max(1, max_chars // 2)
                probe = text[:max_chars]
        except Exception as exc:
            raise RuntimeError("SLM tokenizer could not validate chunk length") from exc
    chunks: list[tuple[int, int, str]] = []
    for parent_start in range(0, len(text), SLM_SOURCE_SPAN_CHARS):
        parent_end = min(len(text), parent_start + SLM_SOURCE_SPAN_CHARS)
        offset = parent_start
        while offset < parent_end:
            end = min(parent_end, offset + max_chars)
            candidate = text[offset:end]
            if tokenizer is not None and isinstance(max_seq_length, int):
                while len(candidate) > 1:
                    try:
                        if (
                            len(
                                tokenizer.encode(
                                    candidate,
                                    add_special_tokens=True,
                                    truncation=False,
                                    verbose=False,
                                )
                            )
                            <= max_seq_length
                        ):
                            break
                    except Exception as exc:
                        raise RuntimeError(
                            "SLM tokenizer could not validate chunk length"
                        ) from exc
                    end = offset + max(1, (end - offset) // 2)
                    candidate = text[offset:end]
            chunks.append((parent_start, offset, candidate))
            offset = end
    return chunks


def _get_all(collection: Any, document_id: str) -> dict[str, list[Any]]:
    ids: list[Any] = []
    documents: list[Any] = []
    metadatas: list[Any] = []
    offset = 0
    while True:
        page = collection.get(
            where={"document_id": {"$eq": document_id}},
            limit=_READ_PAGE_SIZE,
            offset=offset,
            include=["documents", "metadatas"],
        )
        page_ids = page.get("ids") or []
        page_documents = page.get("documents") or []
        page_metadatas = page.get("metadatas") or []
        if len(page_ids) != len(page_documents) or len(page_ids) != len(page_metadatas):
            raise RuntimeError("SLM index read returned incomplete rows")
        if len(set(page_ids)) != len(page_ids) or set(ids).intersection(page_ids):
            raise RuntimeError("SLM index read returned duplicate vector IDs")
        ids.extend(page_ids)
        documents.extend(page_documents)
        metadatas.extend(page_metadatas)
        if len(page_ids) < _READ_PAGE_SIZE:
            break
        offset += len(page_ids)
    return {"ids": ids, "documents": documents, "metadatas": metadatas}


def _expected_index(
    document_id: str,
    source_hash: str,
    model_id: str,
    dimension: int,
    parts: list[tuple[int, int, str]],
):
    layout = hashlib.sha256(
        "|".join(f"{offset}:{len(text)}" for _, offset, text in parts).encode()
    ).hexdigest()
    identity = hashlib.sha256(
        f"{document_id}|{source_hash}|{model_id}|{dimension}|{_CHUNKING_VERSION}|{layout}".encode()
    ).hexdigest()
    entries = []
    for parent_start, offset, text in parts:
        parent_id = f"slm-{parent_start // SLM_SOURCE_SPAN_CHARS + 1:04d}"
        fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()
        vector_id = hashlib.sha256(
            f"{identity}|{offset}|{fingerprint}".encode()
        ).hexdigest()
        entries.append(
            (
                vector_id,
                text,
                {
                    "document_id": document_id,
                    "source_type": "slm",
                    "source_hash": source_hash,
                    "embedding_model": model_id,
                    "embedding_dimension": dimension,
                    "index_identity": identity,
                    "parent_source_id": parent_id,
                    "offset": offset,
                    "text_hash": fingerprint,
                },
            )
        )
    return identity, entries


def _encode_bounded(model: Any, texts: list[str], batch_size: int) -> list[list[float]]:
    """Encode text in bounded batches and reject malformed or non-finite vectors."""
    vectors: list[list[float]] = []
    dimension: int | None = None
    for start in range(0, len(texts), batch_size):
        encoded = model.encode(
            texts[start : start + batch_size],
            batch_size=batch_size,
            show_progress_bar=False,
        )
        if hasattr(encoded, "tolist"):
            encoded = encoded.tolist()
        if not isinstance(encoded, list):
            raise RuntimeError("SLM embedding model returned invalid vectors")
        for vector in encoded:
            if not isinstance(vector, (list, tuple)) or not vector:
                raise RuntimeError("SLM embedding model returned an empty vector")
            if any(
                isinstance(value, bool) or not isinstance(value, Real)
                for value in vector
            ):
                raise RuntimeError("SLM embedding model returned non-numeric values")
            normalized = [float(value) for value in vector]
            if not all(math.isfinite(value) for value in normalized):
                raise RuntimeError("SLM embedding model returned non-finite values")
            if dimension is None:
                dimension = len(normalized)
            elif len(normalized) != dimension:
                raise RuntimeError(
                    "SLM embedding model returned inconsistent dimensions"
                )
            vectors.append(normalized)
        if len(encoded) != min(batch_size, len(texts) - start):
            raise RuntimeError("SLM embedding model returned an incomplete batch")
    return vectors


def _is_complete(
    existing: dict[str, list[Any]], entries: list[tuple[str, str, dict[str, Any]]]
) -> bool:
    by_id = {
        str(vector_id): (text, meta or {})
        for vector_id, text, meta in zip(
            existing["ids"], existing["documents"], existing["metadatas"], strict=False
        )
    }
    expected = {vector_id: (text, meta) for vector_id, text, meta in entries}
    return (
        len(by_id) == len(existing["ids"])
        and all(
            by_id.get(vector_id) == (text, meta)
            for vector_id, (text, meta) in expected.items()
        )
        and len(by_id) == len(expected)
    )


def build_slm_retrieval(
    *,
    document_id: UUID | str,
    canonical_source_text: str,
    queries: Mapping[str, str],
) -> dict[str, Any]:
    """Build/reuse a verified SLM semantic index and return bounded passages."""
    doc_id = str(document_id)
    if not canonical_source_text:
        raise ValueError("canonical_source_text must not be empty")
    if (
        not isinstance(queries, Mapping)
        or not queries
        or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in queries.items()
        )
    ):
        raise ValueError("queries must map criterion codes to query text")
    document_hash = source_hash(canonical_source_text)
    model_id = get_settings().embedding_model_name
    model = get_embedding_model()
    parts = _parts(canonical_source_text, model)
    client = get_chroma_client()
    max_batch = getattr(client, "get_max_batch_size", lambda: 32)()
    batch_size = max(1, min(32, int(max_batch)))
    query_items = list(queries.items())
    if any(not query.strip() for _, query in query_items):
        bad_code = next(code for code, query in query_items if not query.strip())
        raise ValueError(f"query for {bad_code} must not be empty")
    # Query vectors establish the collection dimension without re-encoding an
    # already verified document. A warm evaluation encodes only rubric queries.
    query_vectors = _encode_bounded(
        model, [query for _, query in query_items], batch_size
    )
    dimension = len(query_vectors[0])
    identity, entries = _expected_index(
        doc_id, document_hash, model_id, dimension, parts
    )
    collection_name = resolve_slm_collection_name(model_id, dimension)
    collection = client.get_or_create_collection(
        collection_name, embedding_function=None
    )
    existing = _get_all(collection, doc_id)

    if not _is_complete(existing, entries):
        index_vectors = _encode_bounded(model, [part[2] for part in parts], batch_size)
        if any(len(vector) != dimension for vector in index_vectors):
            raise RuntimeError(
                "SLM index and query embeddings have inconsistent dimensions"
            )
        try:
            for start in range(0, len(entries), batch_size):
                batch = entries[start : start + batch_size]
                collection.upsert(
                    ids=[x[0] for x in batch],
                    documents=[x[1] for x in batch],
                    metadatas=[x[2] for x in batch],
                    embeddings=index_vectors[start : start + batch_size],
                )
            verified = _get_all(collection, doc_id)
            current = {
                str(i): (d, m or {})
                for i, d, m in zip(
                    verified["ids"],
                    verified["documents"],
                    verified["metadatas"],
                    strict=False,
                )
            }
            if any(current.get(i) != (d, m) for i, d, m in entries):
                raise RuntimeError("SLM index verification failed after write")
        except Exception as exc:
            # A client may partially accept a batch before raising.
            try:
                cleanup_ids = [entry[0] for entry in entries]
                for start in range(0, len(cleanup_ids), batch_size):
                    batch_ids = cleanup_ids[start : start + batch_size]
                    collection.delete(ids=batch_ids)
                    remaining = (
                        collection.get(ids=batch_ids, include=[], limit=batch_size).get(
                            "ids"
                        )
                        or []
                    )
                    if remaining:
                        raise RuntimeError("partial SLM index cleanup was incomplete")
            except Exception:
                raise RuntimeError(
                    "SLM index write failed and partial cleanup failed"
                ) from exc
            raise
        # Keep older verified generation until the new one has passed integrity checks.
        collection.delete(
            where={
                "$and": [
                    {"document_id": {"$eq": doc_id}},
                    {"index_identity": {"$ne": identity}},
                ]
            }
        )
        remaining = _get_all(collection, doc_id)
        if not _is_complete(remaining, entries):
            raise RuntimeError("stale SLM index generation cleanup failed")

    parent_order = [
        f"slm-{i + 1:04d}"
        for i in range(
            (len(canonical_source_text) + SLM_SOURCE_SPAN_CHARS - 1)
            // SLM_SOURCE_SPAN_CHARS
        )
    ]
    rankings: dict[str, list[str]] = {}
    passages: dict[str, dict[str, int]] = {}
    for (code, _query), vector in zip(query_items, query_vectors, strict=True):
        result = collection.query(
            query_embeddings=[vector],
            n_results=min(_RESULT_LIMIT, len(entries)),
            where={
                "$and": [
                    {"document_id": {"$eq": doc_id}},
                    {"source_type": {"$eq": "slm"}},
                    {"source_hash": {"$eq": document_hash}},
                    {"embedding_model": {"$eq": model_id}},
                    {"index_identity": {"$eq": identity}},
                ]
            },
            include=["documents", "metadatas", "distances"],
        )
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        returned_ids = (result.get("ids") or [[]])[0]
        if not docs:
            raise RuntimeError(
                f"SLM semantic query returned no indexed chunks for {code}"
            )
        if len(returned_ids) != len(docs) or len(metas) != len(docs):
            raise RuntimeError("SLM semantic query returned incomplete rows")
        seen: set[str] = set()
        ranked: list[str] = []
        expected_by_id = {vector_id: (text, meta) for vector_id, text, meta in entries}
        for vector_id, text, meta in zip(returned_ids, docs, metas, strict=False):
            if (
                not isinstance(meta, dict)
                or meta.get("document_id") != doc_id
                or meta.get("source_hash") != document_hash
                or meta.get("embedding_model") != model_id
                or meta.get("index_identity") != identity
            ):
                raise RuntimeError("SLM semantic query returned an out-of-scope result")
            if meta.get("parent_source_id") not in parent_order:
                raise RuntimeError(
                    "SLM semantic query returned an unknown parent source ID"
                )
            if vector_id not in expected_by_id or expected_by_id[vector_id] != (
                text,
                meta,
            ):
                raise RuntimeError(
                    "SLM semantic query returned an unknown or altered index row"
                )
            if not isinstance(text, str) or hashlib.sha256(
                text.encode("utf-8")
            ).hexdigest() != meta.get("text_hash"):
                raise RuntimeError("SLM semantic query returned tampered indexed text")
            if vector_id not in seen:
                offset = meta.get("offset")
                if isinstance(offset, bool) or not isinstance(offset, int):
                    raise RuntimeError("SLM semantic query returned invalid offset")
                ranked.append(vector_id)
                seen.add(vector_id)
                passages[vector_id] = {"start": offset, "end": offset + len(text)}
                if len(ranked) == _RESULT_LIMIT:
                    break
        rankings[code] = ranked
    result = {
        "contract": "slm_retrieval.v2",
        "document_id": doc_id,
        "source_hash": document_hash,
        "embedding_model": model_id,
        "rankings": rankings,
    }
    result["passages"] = passages
    return result


__all__ = ["build_slm_retrieval"]
