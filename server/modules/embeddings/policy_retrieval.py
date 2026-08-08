"""Local policy retrieval foundation for ITSO evidence tools.

Provides deterministic, bounded policy chunk retrieval from Chroma's
``col_policy_all`` collection. Maps ITSO standard identifiers to policy
areas and returns structured prompt-time evidence with provenance-safe
hashes. All errors fail open to ``unavailable``; no raw policy text,
document/chunk IDs, raw criterion IDs, or filters appear in log messages.
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Any, Final, Literal

from server.core.chroma import get_chroma_client
from server.modules.embeddings.collections import COL_POLICY_ALL

logger = logging.getLogger(__name__)

# Constants — log-safe category labels only (no raw IDs in messages)
_LOG_CAT_ALLOWLIST: Final[str] = "policy:allowlist"
_LOG_CAT_QUERY: Final[str] = "policy:chroma_query"
_LOG_CAT_VALIDATION: Final[str] = "policy:post_validation"
_LOG_CAT_MAP: Final[str] = "policy:criteria"
_LOG_CAT_COLLECTION: Final[str] = "policy:collection"

ITSO_POLICY_MAP: Final[dict[str, tuple[str, ...]]] = {
    "ITSO-03": ("intellectual_property", "general_itso"),
    "ITSO-04": ("data_privacy", "general_itso"),
    "ITSO-05": ("academic_rights", "general_itso"),
}

_DEFAULT_MAX_CHUNKS_PER_CRITERION: Final[int] = 5

# Immutable result contracts


@dataclass(frozen=True, slots=True)
class PolicyEvidenceChunk:
    """A single policy chunk bound for prompt-time evidence."""

    chunk_id: str
    document_id: str
    text: str
    policy_area: str
    page_number: int | None
    token_count: int | None
    distance: float


@dataclass(frozen=True, slots=True)
class PolicyRetrievalResult:
    """Structured policy retrieval outcome for one criterion.

    ``provenance_hash`` is a deterministic SHA-256 hash over all returned
    chunk text, metadata, and identifiers in sorted order. Output retains
    only the opaque hex digest — no raw identifiers or text.
    """

    policy_area: str
    status: Literal["available", "unavailable"]
    chunks: tuple[PolicyEvidenceChunk, ...]
    provenance_hash: str

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


# Core retrieval


def retrieve_policy_context(
    itso_criterion_id: str,
    query_embedding: list[float],
    db: Any | None = None,
    *,
    max_chunks: int = _DEFAULT_MAX_CHUNKS_PER_CRITERION,
) -> PolicyRetrievalResult:
    """Retrieve bounded policy context for an ITSO criterion.

    Maps the criterion to its policy area(s), delegates to the document
    service for a health allowlist, then queries Chroma with metadata
    filters. Validates candidate chunk IDs post-query against the same
    contract. Returns structured evidence with an opaque provenance hash.
    All errors fail open to ``unavailable``.
    """
    policy_areas = ITSO_POLICY_MAP.get(itso_criterion_id)
    if not policy_areas:
        logger.warning("%s unknown criterion", _LOG_CAT_MAP)
        return _unavailable_result(policy_area="unknown")

    if db is None:
        return _unavailable_result(policy_area=policy_areas[0])

    # Clamp max_chunks to safe bounds [1..5].
    max_chunks = max(1, min(max_chunks, _DEFAULT_MAX_CHUNKS_PER_CRITERION))

    # Delegate allowlist to the document-service contract.
    try:
        from server.modules.documents.policy_service import get_healthy_policy_allowlist

        allowlist = get_healthy_policy_allowlist(db)
    except Exception:
        logger.warning("%s build failed", _LOG_CAT_ALLOWLIST)
        return _unavailable_result(policy_area=policy_areas[0])

    # Try primary area first, then fallback areas.
    for area in policy_areas:
        document_ids = allowlist.get(area)
        if not document_ids:
            continue

        result = _query_policy_area(
            area,
            list(document_ids),
            query_embedding,
            db=db,
            max_chunks=max_chunks,
        )
        if result.status == "available":
            return result

    return _unavailable_result(policy_area=policy_areas[0])


def _query_policy_area(
    policy_area: str,
    document_ids: list[str],
    query_embedding: list[float],
    *,
    db: Any,
    max_chunks: int = _DEFAULT_MAX_CHUNKS_PER_CRITERION,
) -> PolicyRetrievalResult:
    """Query Chroma ``col_policy_all`` and post-validate results.

    Filters by policy area and the allowlist of healthy document IDs.
    Post-validates every candidate chunk ID against the document-service
    contract (existing, healthy doc, chroma_stored).
    """
    try:
        collection = get_chroma_client().get_collection(COL_POLICY_ALL)
    except Exception:
        logger.warning("%s cannot access col_policy_all", _LOG_CAT_COLLECTION)
        return _unavailable_result(policy_area=policy_area)

    # Dual metadata filter: policy area + document allowlist.
    if not document_ids:
        return _unavailable_result(policy_area=policy_area)

    where_filter: dict[str, Any] = {
        "$and": [
            {"policy_area": {"$eq": policy_area}},
            {"document_id": {"$in": document_ids}},
        ]
    }

    # Request extra results to account for post-validation filtering.
    query_n = min(max_chunks * 3, 50)

    try:
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=query_n,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        logger.warning("%s query failed", _LOG_CAT_QUERY)
        return _unavailable_result(policy_area=policy_area)

    try:
        from server.modules.documents.policy_service import validate_policy_chunks

        raw_chunks = _parse_policy_chunks(result)
        # Build tuples for validation: (chunk_id, document_id, policy_area)
        candidate_tuples = [
            (c.chunk_id, c.document_id, c.policy_area) for c in raw_chunks
        ]
        valid_ids = set(validate_policy_chunks(candidate_tuples, db))
        chunks = [c for c in raw_chunks if c.chunk_id in valid_ids]
    except Exception:
        logger.warning("%s post-validation failed", _LOG_CAT_VALIDATION)
        return _unavailable_result(policy_area=policy_area)

    if not chunks:
        return _unavailable_result(policy_area=policy_area)

    # Deterministic ranking: distance (ascending) then chunk_id (ascending).
    chunks.sort(key=lambda c: (c.distance, c.chunk_id))

    selected = tuple(chunks[:max_chunks])
    provenance_hash = _build_provenance_hash(selected)

    return PolicyRetrievalResult(
        policy_area=policy_area,
        status="available",
        chunks=selected,
        provenance_hash=provenance_hash,
    )


# Parsing and validation


def _parse_policy_chunks(chroma_result: dict[str, Any]) -> list[PolicyEvidenceChunk]:
    """Parse and validate Chroma results into ``PolicyEvidenceChunk`` list.

    Entries with missing/invalid metadata, empty text, or non-finite
    distances are silently skipped. All failures fail open (skip, not
    raise).
    """
    documents = (chroma_result.get("documents") or [[]])[0]
    metadatas = (chroma_result.get("metadatas") or [[]])[0]
    distances = (chroma_result.get("distances") or [[]])[0]

    parsed: list[PolicyEvidenceChunk] = []
    for index, text in enumerate(documents):
        # Validate text content.
        if not text or not isinstance(text, str) or not text.strip():
            continue

        metadata = metadatas[index] if index < len(metadatas) else {}
        metadata = metadata or {}

        # Required metadata fields — skip if any are missing.
        chunk_id = metadata.get("chunk_id")
        doc_id = metadata.get("document_id")
        p_area = metadata.get("policy_area")
        if not chunk_id or not doc_id or not p_area:
            continue

        distance = distances[index] if index < len(distances) else 0.0
        # Guard against non-finite distances.
        try:
            dist_float = float(distance)
            if math.isnan(dist_float) or math.isinf(dist_float):
                continue
        except (TypeError, ValueError):
            continue

        parsed.append(
            PolicyEvidenceChunk(
                chunk_id=str(chunk_id),
                document_id=str(doc_id),
                text=str(text),
                policy_area=str(p_area),
                page_number=metadata.get("page_number"),
                token_count=metadata.get("token_count"),
                distance=dist_float,
            )
        )
    return parsed


# Provenance helper


def _build_provenance_hash(chunks: tuple[PolicyEvidenceChunk, ...]) -> str:
    """Build a deterministic SHA-256 hash from ordered chunk text + metadata.

    The hash covers the canonical clause text, chunk_id, document_id,
    policy_area, page_number, and token_count for each chunk in sorted
    order. Output retains only the opaque hex digest — no raw identifiers
    or text. Changed text produces a different hash.
    """
    if not chunks:
        return hashlib.sha256(b"empty").hexdigest()

    parts: list[str] = []
    for c in chunks:
        parts.append(
            f"text={c.text}|chunk_id={c.chunk_id}|doc_id={c.document_id}"
            f"|area={c.policy_area}|page={c.page_number}|tokens={c.token_count}"
        )
    canonical = "||".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _unavailable_result(policy_area: str) -> PolicyRetrievalResult:
    """Return a safe ``unavailable`` result with a stable empty-state hash."""
    return PolicyRetrievalResult(
        policy_area=policy_area,
        status="unavailable",
        chunks=(),
        provenance_hash=hashlib.sha256(b"empty").hexdigest(),
    )


__all__ = [
    "ITSO_POLICY_MAP",
    "PolicyEvidenceChunk",
    "PolicyRetrievalResult",
    "retrieve_policy_context",
]
