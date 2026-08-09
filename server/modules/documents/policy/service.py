"""Policy-specific lifecycle, health, and validation predicates.

Keeps policy logic out of the general document service, avoiding duplicate
400-line blocks. Provides two health tiers:

* ``is_source_healthy_policy_document`` — source/rebuildable health: file
  exists on disk, ``PROCESSED``, has chunks, valid ``policy_area``.
* ``is_retrieval_ready_policy_document`` — retrieval readiness: all of the
  above plus at least one ``chroma_stored`` chunk whose ``policy_area``
  matches the parent document.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any

from server.modules.embeddings.service import check_chroma_availability

from .. import persistence
from ..exceptions import (
    DocumentNotFoundError,
    ReferenceDeleteInvalidTypeError,
    ReferenceRebuildError,
)
from ..models import VALID_POLICY_AREAS, Document, DocumentChunk
from ..schemas import (
    POLICY_SOURCE_TYPES,
    PolicyDeleteResponse,
    PolicyLibraryItem,
    PolicyLibraryResponse,
    PolicyRebuildResponse,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier 1: source/rebuildable health
# ---------------------------------------------------------------------------


def is_source_healthy_policy_document(doc: Any, db: Any) -> bool:
    """Return True if *doc* is eligible for rebuild.

    Source health requires ALL of:

    * ``source_type`` is ``"policy"``
    * ``policy_area`` is in the canonical ``VALID_POLICY_AREAS`` set
    * ``processing_status`` is ``"PROCESSED"``
    * At least one ``DocumentChunk`` row exists (regardless of ``chroma_stored``)
    * The local uploaded PDF file exists on disk (``Path.is_file()``)
    """
    if doc.source_type != "policy":
        return False
    if doc.policy_area not in VALID_POLICY_AREAS:
        return False
    if doc.processing_status != "PROCESSED":
        return False
    if not doc.file_path:
        return False
    if not Path(doc.file_path).is_file():
        return False
    chunk_count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc.document_id)
        .count()
    )
    if chunk_count == 0:
        return False
    return True


def is_retrieval_ready_policy_document(doc: Any, db: Any) -> bool:
    """Return True if *doc* is ready for retrieval.

    Retrieval readiness requires ALL of ``is_source_healthy_policy_document``
    PLUS at least one ``chroma_stored`` chunk whose ``policy_area`` matches
    the parent document's ``policy_area``.
    """
    if not is_source_healthy_policy_document(doc, db):
        return False
    matching_chunks = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == doc.document_id,
            DocumentChunk.chroma_stored == True,  # noqa: E712
            DocumentChunk.policy_area == doc.policy_area,
        )
        .count()
    )
    return matching_chunks > 0


# ---------------------------------------------------------------------------
# Allowlist for retrieval
# ---------------------------------------------------------------------------


def get_healthy_policy_allowlist(db: Any) -> dict[str, set[str]]:
    """Return ``{policy_area: {document_id, ...}}`` of retrieval-ready policy docs.

    Uses :func:`is_retrieval_ready_policy_document` as the predicate. The result
    is a dict keyed by policy area for direct lookup during retrieval. Missing
    or empty areas are omitted.
    """
    rows = (
        db.query(Document)
        .filter(
            Document.source_type == "policy",
            Document.policy_area.in_(VALID_POLICY_AREAS),
            Document.processing_status == "PROCESSED",
        )
        .all()
    )

    allowlist: dict[str, set[str]] = {}
    for row in rows:
        if not is_retrieval_ready_policy_document(row, db):
            continue
        area = row.policy_area
        if area not in VALID_POLICY_AREAS:
            continue
        allowlist.setdefault(area, set()).add(str(row.document_id))

    return allowlist


# ---------------------------------------------------------------------------
# Chunk validation — complete (chunk_id, document_id, policy_area) tuple
# ---------------------------------------------------------------------------


def _opaque_id(candidate: str) -> str:
    """Return a stable opaque hash for a candidate identifier.

    Used instead of logging raw chunk/doc IDs.
    """
    return hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:12]


def validate_policy_chunks(
    chunk_tuples: list[tuple[str, str, str]],
    db: Any,
) -> list[str]:
    """Validate each (chunk_id, document_id, policy_area) tuple from Chroma
    against SQL. Returns chunk IDs whose complete tuple matches a retrieval-ready
    policy document in SQL. Any tuple mismatch or missing metadata is excluded.

    Raw invalid criterion, IDs, text, and paths are never logged.
    """
    if not chunk_tuples:
        return []

    # Separate valid UUIDs; silently skip non-UUID garbage.
    valid: list[tuple[uuid.UUID, str, str]] = []
    for cid_str, did_str, area_str in chunk_tuples:
        try:
            cid = uuid.UUID(cid_str)
        except (ValueError, TypeError):
            continue
        if not did_str or not area_str:
            continue
        valid.append((cid, did_str, area_str))

    if not valid:
        return []

    chunk_ids = [v[0] for v in valid]
    rows = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.chunk_id.in_(chunk_ids),
            DocumentChunk.source_type == "policy",
        )
        .all()
    )
    if not rows:
        return []

    # Build SQL truth: chunk_id -> (document_id, policy_area)
    sql_map: dict[uuid.UUID, tuple[uuid.UUID, str | None]] = {
        r.chunk_id: (r.document_id, r.policy_area) for r in rows
    }

    doc_ids = {r.document_id for r in rows if r.document_id}
    if not doc_ids:
        return []

    # Parent documents must be source-healthy
    healthy_docs = (
        db.query(Document)
        .filter(
            Document.document_id.in_(doc_ids),
            Document.source_type == "policy",
            Document.policy_area.in_(VALID_POLICY_AREAS),
            Document.processing_status == "PROCESSED",
        )
        .all()
    )
    healthy_doc_ids = set()
    doc_policy_map: dict[uuid.UUID, str | None] = {}
    for doc in healthy_docs:
        if doc.file_path and Path(doc.file_path).is_file():
            healthy_doc_ids.add(doc.document_id)
            doc_policy_map[doc.document_id] = doc.policy_area

    # Validate each Chroma tuple against SQL truth
    result: list[str] = []
    for cid, chroma_did, chroma_area in valid:
        sql_entry = sql_map.get(cid)
        if sql_entry is None:
            continue  # chunk_id not in SQL at all
        sql_did, sql_area = sql_entry

        # document_id must match
        if str(sql_did) != chroma_did:
            continue
        # Parent document must be healthy
        if sql_did not in healthy_doc_ids:
            continue
        # policy_area must match SQL
        expected_area = doc_policy_map.get(sql_did)
        if chroma_area != expected_area:
            continue
        # SQL chunk policy_area must also match
        if sql_area is not None and sql_area != expected_area:
            continue

        result.append(str(cid))

    return result


# ---------------------------------------------------------------------------
# Admin library listing
# ---------------------------------------------------------------------------


def list_policy_documents(db: Any | None = None) -> PolicyLibraryResponse:
    """Admin-only listing of policy documents with computed health."""
    if db is None:
        return PolicyLibraryResponse(items=[], total=0)

    rows = (
        db.query(Document)
        .filter(Document.source_type.in_(POLICY_SOURCE_TYPES))
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    items: list[PolicyLibraryItem] = []
    for row in rows:
        chunk_count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == row.document_id)
            .count()
        )
        file_exists = Path(row.file_path).is_file() if row.file_path else False
        chroma_available = check_chroma_availability(
            str(row.document_id), row.source_type
        )
        source_healthy = is_source_healthy_policy_document(row, db)
        retrieval_ready = is_retrieval_ready_policy_document(row, db)
        items.append(
            PolicyLibraryItem(
                document_id=row.document_id,
                title=row.title,
                source_type=row.source_type,
                policy_area=row.policy_area,
                program=row.program,
                course_code=row.course_code,
                academic_year=row.academic_year,
                page_count=row.page_count,
                uploaded_at=row.uploaded_at,
                uploaded_by=row.uploaded_by,
                processing_status=row.processing_status,
                file_exists=file_exists,
                chunk_count=chunk_count,
                chroma_available=chroma_available,
                embedding_ready=retrieval_ready,
                source_healthy=source_healthy,
            )
        )

    return PolicyLibraryResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Delete — DB-authoritative ordering
# ---------------------------------------------------------------------------


def delete_policy_document(
    document_id: uuid.UUID,
    db: Any | None = None,
) -> PolicyDeleteResponse:
    """Admin-only delete of a policy document.

    DB-authoritative: commits SQL removal/transition FIRST, then performs
    external Chroma/PDF cleanup only after authoritative DB state is
    committed. A commit failure cannot destroy live assets.
    """
    if db is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    from server.modules.embeddings.service import delete_chroma_vectors

    row = db.get(Document, document_id)
    if row is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    details: dict[str, object] = {}

    # Validate source type
    if row.source_type not in POLICY_SOURCE_TYPES:
        raise ReferenceDeleteInvalidTypeError(
            f"Document {document_id} has source_type='{row.source_type}'; "
            "only policy documents can be deleted through this endpoint."
        )

    file_path_backup = row.file_path

    # Step 1 — SQL removal (DB-authoritative). Commit first.
    chunk_count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .delete()
    )
    details["chunks_deleted"] = chunk_count
    db.delete(row)
    db.commit()  # Authoritative — external cleanup only follows success

    # Step 2 — External cleanup (best-effort, after commit)
    try:
        deleted_chroma = delete_chroma_vectors(str(document_id), "policy")
        details["chroma_deleted"] = deleted_chroma
    except Exception as exc:
        logger.warning(
            "Chroma deletion reported an issue during policy cleanup",
            extra={"document_id": str(document_id)},
        )
        details["chroma_warning"] = str(exc)

    if file_path_backup:
        pdf_path = Path(file_path_backup)
        if pdf_path.exists():
            try:
                pdf_path.unlink()
                details["file_deleted"] = True
            except OSError as exc:
                logger.warning(
                    "Failed to delete local PDF file during policy cleanup",
                    extra={"document_id": str(document_id)},
                )
                details["file_warning"] = str(exc)
        else:
            details["file_missing"] = True
    else:
        details["file_missing"] = True

    return PolicyDeleteResponse(
        document_id=document_id,
        deleted=True,
        details=details,
    )


# ---------------------------------------------------------------------------
# Rebuild embeddings
# ---------------------------------------------------------------------------


def rebuild_policy_embeddings(
    document_id: uuid.UUID,
    db: Any | None = None,
) -> PolicyRebuildResponse:
    """Admin-only rebuild of Chroma embeddings for a policy document
    from stored chunks with deterministic ordering by chunk_index."""
    if db is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    from server.modules.embeddings.service import embed_and_store_chunks

    row = db.get(Document, document_id)
    if row is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")

    if row.source_type not in POLICY_SOURCE_TYPES:
        raise ReferenceRebuildError(
            f"Rebuild is only supported for policy documents, not {row.source_type}."
        )

    if not is_source_healthy_policy_document(row, db):
        raise ReferenceRebuildError("Document is not eligible for rebuild.")

    chunks = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == document_id,
            DocumentChunk.source_type == "policy",
        )
        .order_by(
            DocumentChunk.chunk_index.asc().nullsfirst(),
            DocumentChunk.page_number.asc(),
            DocumentChunk.created_at.asc(),
        )
        .all()
    )
    if not chunks:
        raise ReferenceRebuildError(
            f"Document {document_id} has no stored chunks to rebuild embeddings from."
        )

    upserted = embed_and_store_chunks(chunks)
    if db is not None and upserted:
        persistence.mark_chunks_chroma_stored(db, [chunk.chunk_id for chunk in chunks])
    return PolicyRebuildResponse(
        document_id=document_id,
        rebuilt=upserted > 0,
        chunk_count=len(chunks),
        details={"chunks_upserted": upserted},
    )


__all__ = [
    "is_source_healthy_policy_document",
    "is_retrieval_ready_policy_document",
    "get_healthy_policy_allowlist",
    "validate_policy_chunks",
    "list_policy_documents",
    "delete_policy_document",
    "rebuild_policy_embeddings",
]
