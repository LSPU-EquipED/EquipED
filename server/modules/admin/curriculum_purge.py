"""Admin service for purging retired curriculum references.

Removes curriculum reference documents (``source_type == "curriculum"``)
together with their persisted chunk rows, scoped Chroma vectors in the shared
reference collection, and local PDF artifacts — while preserving evaluation
history. Evaluation jobs that pointed at a purged curriculum keep their
``curriculum_id`` pointer cleared to NULL and their partial-evaluation flags
are never touched.

Design guarantees:

- ``plan_curriculum_purge`` is strictly non-mutating and reports blockers
  instead of raising.
- ``execute_curriculum_purge`` fails closed: database / Chroma / upload-root
  must be reachable, every curriculum PDF path must be root-contained,
  non-symlink, and unique, and no active evaluation job may reference a
  purged curriculum.
- The database mutation is one SQL transaction that clears nullable
  ``EvaluationFlag.chunk_id`` pointers and ``curriculum_id`` job pointers,
  then deletes chunk rows and document rows. The transaction commits only
  AFTER external cleanup (scoped vector deletion in ``col_reference_all``
  and local PDF deletion) has fully succeeded and been strictly verified
  (zero scoped vectors remaining, files gone). Any cleanup failure aborts
  before commit, rolls the database back, and raises — the purge never
  commits SQL and then silently leaves unretryable orphans.
- The returned JSON manifest is content-free: it carries document ids and
  counts only, never chunk or extracted text.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from server.core.chroma import get_chroma_client
from server.modules.documents.models import Document, DocumentChunk
from server.modules.embeddings.collections import COL_REFERENCE_ALL
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import EvaluationFlag
from sqlalchemy import func, text

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_UPLOAD_ROOT = _PROJECT_ROOT / "uploads"

# Terminal lifecycle states. Jobs or documents still in any other state are
# considered active and block the purge.
TERMINAL_JOB_STATUSES = ("COMPLETED", "FAILED")
TERMINAL_DOC_PROCESSING_STATUSES = ("PROCESSED", "FAILED")

SCHEMA_VERSION = 1


class PurgeError(Exception):
    """Base class for curriculum purge failures."""


class PurgeUnreachableError(PurgeError):
    """Raised when a required dependency cannot be reached."""


class PurgeBlockedError(PurgeError):
    """Raised when pre-flight safety checks prevent the purge."""


class PurgeExecutionError(PurgeError):
    """Raised when post-commit external cleanup cannot be strictly verified."""


# ---------------------------------------------------------------------------
# Reachability
# ---------------------------------------------------------------------------


def _resolve_upload_root(upload_root: str | Path | None) -> Path:
    if upload_root is None:
        return DEFAULT_UPLOAD_ROOT
    return Path(upload_root)


def _check_database(db: Any) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_chroma(chroma_client: Any | None) -> bool:
    try:
        client = chroma_client if chroma_client is not None else get_chroma_client()
        client.heartbeat()
        return True
    except Exception:
        return False


def _reachability(
    db: Any, root: Path, chroma_client: Any | None
) -> tuple[dict[str, bool], list[str]]:
    """Return (checks, issues). Fail-closed reachability gate."""
    db_ok = _check_database(db)
    chroma_ok = _check_chroma(chroma_client)
    root_ok = root.is_dir()
    checks = {
        "database": db_ok,
        "chroma": chroma_ok,
        "upload_root": root_ok,
    }
    issues: list[str] = []
    if not db_ok:
        issues.append("database unreachable")
    if not chroma_ok:
        issues.append("chroma unreachable")
    if not root_ok:
        issues.append(f"upload root is not a directory: {root}")
    return checks, issues


# ---------------------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------------------


def _curriculum_documents(db: Any) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.source_type == "curriculum")
        .order_by(Document.document_id.asc())
        .all()
    )


def _job_reference_counts(
    db: Any, doc_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Return number of evaluation jobs referencing each curriculum id."""
    if not doc_ids:
        return {}
    rows = (
        db.query(EvaluationJob.curriculum_id, func.count())
        .filter(EvaluationJob.curriculum_id.in_(doc_ids))
        .group_by(EvaluationJob.curriculum_id)
        .all()
    )
    return {curriculum_id: count for curriculum_id, count in rows}


def _active_job_curricula(db: Any, doc_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Return curriculum ids referenced by non-terminal evaluation jobs."""
    if not doc_ids:
        return []
    rows = (
        db.query(EvaluationJob.curriculum_id)
        .filter(
            EvaluationJob.curriculum_id.in_(doc_ids),
            EvaluationJob.status.not_in(TERMINAL_JOB_STATUSES),
        )
        .all()
    )
    return [row[0] for row in rows]


def _chunk_counts(db: Any, doc_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not doc_ids:
        return {}
    rows = (
        db.query(DocumentChunk.document_id, func.count())
        .filter(DocumentChunk.document_id.in_(doc_ids))
        .group_by(DocumentChunk.document_id)
        .all()
    )
    return {document_id: count for document_id, count in rows}


def _all_document_paths(db: Any, root: Path) -> dict[Path, list[uuid.UUID]]:
    """Map resolved absolute PDF paths to every document id claiming them."""
    root_parent = root.resolve().parent
    mapping: dict[Path, list[uuid.UUID]] = {}
    rows = db.query(Document.document_id, Document.file_path).all()
    for document_id, file_path in rows:
        if not file_path:
            continue
        candidate = Path(file_path)
        if not candidate.is_absolute():
            candidate = root_parent / candidate
        mapping.setdefault(candidate.resolve(), []).append(document_id)
    return mapping


def _assess_path(
    doc: Document,
    root: Path,
    all_paths: dict[Path, list[uuid.UUID]],
) -> dict[str, Any]:
    """Validate a stored file path: root-contained, non-symlink, unique PDF.

    Missing files are tolerated (already deleted) and never fail the check;
    only structurally unsafe paths block the purge.
    """
    root_resolved = root.resolve()
    raw = doc.file_path or ""
    if not raw:
        return {
            "relative_path": "",
            "resolved_path": "",
            "inside_upload_root": False,
            "is_pdf": False,
            "symlink": False,
            "unique": True,
            "exists": False,
            "safe": False,
            "reason": "missing_file_path",
        }
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root_resolved.parent / candidate
    symlink = candidate.is_symlink()
    resolved = candidate.resolve()
    inside_root = resolved == root_resolved or root_resolved in resolved.parents
    is_pdf = resolved.suffix.lower() == ".pdf"
    unique = all(
        other == doc.document_id for other in all_paths.get(resolved, [doc.document_id])
    )
    safe = inside_root and not symlink and is_pdf and unique

    reasons: list[str] = []
    if not inside_root:
        reasons.append("outside_upload_root")
    if symlink:
        reasons.append("symlink")
    if not is_pdf:
        reasons.append("not_pdf")
    if not unique:
        reasons.append("shared_path")

    return {
        "relative_path": raw,
        "resolved_path": str(resolved),
        "inside_upload_root": inside_root,
        "is_pdf": is_pdf,
        "symlink": symlink,
        "unique": unique,
        "exists": resolved.exists(),
        "safe": safe,
        "reason": ",".join(reasons) if reasons else "",
    }


# ---------------------------------------------------------------------------
# Scoped vector deletion (shared reference collection)
# ---------------------------------------------------------------------------


def _vector_counts(
    chroma_client: Any | None, doc_ids: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, int], bool]:
    """Return (count per document, collection_present) for the shared collection.

    Never raises: an unreachable client or a missing collection is reported
    as absent so dry-run planning can proceed.
    """
    counts: dict[uuid.UUID, int] = {}
    if not doc_ids:
        return counts, False
    try:
        client = chroma_client if chroma_client is not None else get_chroma_client()
        collection = client.get_collection(COL_REFERENCE_ALL)
    except Exception:
        return counts, False
    for doc_id in doc_ids:
        try:
            result = collection.get(where={"document_id": {"$eq": str(doc_id)}})
            counts[doc_id] = len(result.get("ids", []))
        except Exception:
            counts[doc_id] = 0
    return counts, True


def _is_missing_collection(exc: Exception) -> bool:
    """Return True when Chroma reports the shared collection does not exist."""
    return type(exc).__name__ == "NotFoundError"


def _delete_vectors_strict(
    chroma_client: Any | None, doc_ids: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, int], bool]:
    """Delete scoped vectors in the shared collection and verify zero remain.

    The deletion is scoped by document id inside ``col_reference_all`` so
    syllabus vectors and every other document's vectors in the shared
    collection are preserved. Fail-closed: any Chroma get/delete error or a
    leftover vector raises :class:`PurgeExecutionError`. The only tolerated
    "absence" is a genuinely missing collection (nothing was ever embedded),
    which is reported through the returned ``collection_present`` flag.

    Returns (deleted count per document, collection_present).
    """
    deleted: dict[uuid.UUID, int] = {}
    if not doc_ids:
        return deleted, False
    try:
        client = chroma_client if chroma_client is not None else get_chroma_client()
        collection = client.get_collection(COL_REFERENCE_ALL)
    except Exception as exc:
        if _is_missing_collection(exc):
            return deleted, False
        raise PurgeExecutionError(
            f"vector cleanup failed: cannot open shared collection "
            f"{COL_REFERENCE_ALL}: {type(exc).__name__}: {exc}"
        ) from exc
    for doc_id in doc_ids:
        try:
            result = collection.get(where={"document_id": {"$eq": str(doc_id)}})
        except Exception as exc:
            raise PurgeExecutionError(
                f"vector cleanup failed: cannot query vectors for {doc_id}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        ids = result.get("ids", [])
        if ids:
            try:
                collection.delete(ids=ids)
            except Exception as exc:
                raise PurgeExecutionError(
                    f"vector cleanup failed: cannot delete {len(ids)} vectors "
                    f"for {doc_id}: {type(exc).__name__}: {exc}"
                ) from exc
        try:
            remaining = collection.get(
                where={"document_id": {"$eq": str(doc_id)}}
            )
        except Exception as exc:
            raise PurgeExecutionError(
                f"vector cleanup verification failed for {doc_id}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        leftovers = remaining.get("ids", [])
        if leftovers:
            raise PurgeExecutionError(
                f"vector cleanup verification failed: {len(leftovers)} vectors "
                f"remain for {doc_id} after deletion"
            )
        deleted[doc_id] = len(ids)
    return deleted, True


def _delete_files_strict(
    curricula: list[Document],
    path_infos: dict[uuid.UUID, dict[str, Any]],
) -> tuple[int, int]:
    """Delete local PDFs and verify they are gone. Returns (deleted, missing).

    Fail-closed: an unlink failure (other than the file already being gone)
    or a leftover file raises :class:`PurgeExecutionError`. Missing files are
    tolerated and counted, matching the path-safety semantics.
    """
    files_deleted = 0
    files_missing = 0
    for doc in curricula:
        info = path_infos[doc.document_id]
        resolved = Path(info.get("resolved_path", ""))
        if not info.get("exists") or not resolved:
            files_missing += 1
            continue
        try:
            resolved.unlink()
        except FileNotFoundError:
            files_missing += 1
            continue
        except OSError as exc:
            raise PurgeExecutionError(
                f"file cleanup failed: cannot delete {resolved}: {exc}"
            ) from exc
        if resolved.exists():
            raise PurgeExecutionError(
                f"file cleanup verification failed: {resolved} still exists"
            )
        files_deleted += 1
    return files_deleted, files_missing


# ---------------------------------------------------------------------------
# Manifest composition
# ---------------------------------------------------------------------------


def _compose_manifest(
    *,
    dry_run: bool,
    executed_at: str,
    checks: dict[str, bool],
    blockers: list[str],
    curricula: list[Document],
    job_counts: dict[uuid.UUID, int],
    chunk_counts: dict[uuid.UUID, int],
    path_infos: dict[uuid.UUID, dict[str, Any]],
    vector_counts: dict[uuid.UUID, int],
    collection_present: bool,
    results: dict[str, int] | None = None,
) -> dict[str, Any]:
    items = []
    for doc in curricula:
        doc_id = doc.document_id
        items.append(
            {
                "document_id": str(doc_id),
                "program": doc.program,
                "source_type": doc.source_type,
                "file": path_infos.get(doc_id, {}),
                "chunks": chunk_counts.get(doc_id, 0),
                "jobs_referencing": job_counts.get(doc_id, 0),
                "vectors": vector_counts.get(doc_id, 0),
            }
        )
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "dry_run": dry_run,
        "executed_at": executed_at,
        "checks": checks,
        "blockers": sorted(set(blockers)),
        "collection": COL_REFERENCE_ALL,
        "collection_present": collection_present,
        "curricula": items,
        "totals": {
            "documents": len(items),
            "chunks": sum(item["chunks"] for item in items),
            "jobs_to_clear": sum(item["jobs_referencing"] for item in items),
            "vectors_to_delete": sum(item["vectors"] for item in items),
            "files_to_delete": sum(
                1 for item in items if item["file"].get("exists")
            ),
        },
    }
    if results is not None:
        manifest["results"] = results
    return manifest


def _empty_results() -> dict[str, int]:
    return {
        "flag_chunk_pointers_cleared": 0,
        "jobs_curriculum_cleared": 0,
        "chunks_deleted": 0,
        "documents_deleted": 0,
        "vectors_deleted": 0,
        "files_deleted": 0,
        "files_missing": 0,
        "file_unlink_failures": 0,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plan_curriculum_purge(
    db: Any,
    *,
    upload_root: str | Path | None = None,
    chroma_client: Any | None = None,
) -> dict[str, Any]:
    """Dry-run plan: verify reachability, safety, and report what would change.

    Never mutates the database, the vector store, or the filesystem. All
    findings (including blockers) are returned in the manifest.
    """
    root = _resolve_upload_root(upload_root)
    checks, issues = _reachability(db, root, chroma_client)
    blockers = list(issues)
    db_ok = checks["database"]
    chroma_ok = checks["chroma"]

    curricula = _curriculum_documents(db) if db_ok else []
    doc_ids = [doc.document_id for doc in curricula]
    job_counts = _job_reference_counts(db, doc_ids) if db_ok else {}
    active_job_ids = _active_job_curricula(db, doc_ids) if db_ok else []
    all_paths = _all_document_paths(db, root) if db_ok else {}
    path_infos = {
        doc.document_id: _assess_path(doc, root, all_paths) for doc in curricula
    }
    chunk_counts = _chunk_counts(db, doc_ids) if db_ok else {}

    for doc in curricula:
        info = path_infos[doc.document_id]
        if not info["safe"]:
            blockers.append(
                f"unsafe path for {doc.document_id}: {info['reason']}"
            )
        if doc.processing_status not in TERMINAL_DOC_PROCESSING_STATUSES:
            blockers.append(
                f"curriculum {doc.document_id} still processing "
                f"({doc.processing_status})"
            )
    for doc_id in sorted(set(active_job_ids)):
        blockers.append(
            f"curriculum {doc_id} referenced by an active evaluation job"
        )

    vector_counts, collection_present = ({}, False)
    if chroma_ok:
        vector_counts, collection_present = _vector_counts(chroma_client, doc_ids)

    return _compose_manifest(
        dry_run=True,
        executed_at=datetime.now(UTC).isoformat(),
        checks=checks,
        blockers=blockers,
        curricula=curricula,
        job_counts=job_counts,
        chunk_counts=chunk_counts,
        path_infos=path_infos,
        vector_counts=vector_counts,
        collection_present=collection_present,
    )


def execute_curriculum_purge(
    db: Any,
    *,
    upload_root: str | Path | None = None,
    chroma_client: Any | None = None,
) -> dict[str, Any]:
    """Execute the purge after fail-closed pre-flight checks.

    Raises :class:`PurgeUnreachableError` when a dependency cannot be reached
    and :class:`PurgeBlockedError` when safety checks fail. The database
    mutation is one SQL transaction: nullable ``EvaluationFlag.chunk_id`` and
    ``EvaluationJob.curriculum_id`` pointers are cleared, then chunk rows and
    document rows are deleted. External cleanup (scoped Chroma vectors and
    local PDFs) is strictly verified BEFORE the transaction commits — any
    cleanup failure aborts, rolls the database back, and raises
    :class:`PurgeExecutionError`, so a rerun always succeeds.
    """
    root = _resolve_upload_root(upload_root)
    checks, issues = _reachability(db, root, chroma_client)
    if issues:
        raise PurgeUnreachableError("; ".join(issues))

    curricula = _curriculum_documents(db)
    doc_ids = [doc.document_id for doc in curricula]
    job_counts = _job_reference_counts(db, doc_ids)
    active_job_ids = _active_job_curricula(db, doc_ids)
    all_paths = _all_document_paths(db, root)
    path_infos = {
        doc.document_id: _assess_path(doc, root, all_paths) for doc in curricula
    }
    chunk_counts = _chunk_counts(db, doc_ids)

    blockers: list[str] = []
    for doc in curricula:
        info = path_infos[doc.document_id]
        if not info["safe"]:
            blockers.append(
                f"unsafe path for {doc.document_id}: {info['reason']}"
            )
        if doc.processing_status not in TERMINAL_DOC_PROCESSING_STATUSES:
            blockers.append(
                f"curriculum {doc.document_id} still processing "
                f"({doc.processing_status})"
            )
    for doc_id in sorted(set(active_job_ids)):
        blockers.append(
            f"curriculum {doc_id} referenced by an active evaluation job"
        )
    if blockers:
        raise PurgeBlockedError("; ".join(blockers))

    if not doc_ids:
        return _compose_manifest(
            dry_run=False,
            executed_at=datetime.now(UTC).isoformat(),
            checks=checks,
            blockers=[],
            curricula=curricula,
            job_counts=job_counts,
            chunk_counts=chunk_counts,
            path_infos=path_infos,
            vector_counts={},
            collection_present=False,
            results=_empty_results(),
        )

    # Chunk rows about to be deleted (needed for flag pointer cleanup).
    chunk_id_rows = (
        db.query(DocumentChunk.chunk_id)
        .filter(DocumentChunk.document_id.in_(doc_ids))
        .all()
    )
    chunk_ids = [row[0] for row in chunk_id_rows]

    try:
        # One SQL transaction (uncommitted until external cleanup verifies):
        # clear nullable flag/job pointers, then delete chunk and document
        # rows. Partial-evaluation flags on jobs are never touched.
        if chunk_ids:
            flag_chunk_pointers_cleared = (
                db.query(EvaluationFlag)
                .filter(EvaluationFlag.chunk_id.in_(chunk_ids))
                .update({EvaluationFlag.chunk_id: None}, synchronize_session=False)
            )
        else:
            flag_chunk_pointers_cleared = 0
        jobs_cleared = (
            db.query(EvaluationJob)
            .filter(EvaluationJob.curriculum_id.in_(doc_ids))
            .update({EvaluationJob.curriculum_id: None}, synchronize_session=False)
        )
        chunks_deleted = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id.in_(doc_ids))
            .delete(synchronize_session=False)
        )
        for doc in curricula:
            db.delete(doc)

        # External cleanup must fully succeed and be verified before commit.
        # Failures raise PurgeExecutionError and roll the transaction back.
        vector_counts, collection_present = _delete_vectors_strict(
            chroma_client, doc_ids
        )
        files_deleted, files_missing = _delete_files_strict(curricula, path_infos)

        db.commit()
    except Exception:
        db.rollback()
        raise

    results = {
        "flag_chunk_pointers_cleared": flag_chunk_pointers_cleared,
        "jobs_curriculum_cleared": jobs_cleared,
        "chunks_deleted": chunks_deleted,
        "documents_deleted": len(doc_ids),
        "vectors_deleted": sum(vector_counts.values()),
        "files_deleted": files_deleted,
        "files_missing": files_missing,
        "file_unlink_failures": 0,
    }
    return _compose_manifest(
        dry_run=False,
        executed_at=datetime.now(UTC).isoformat(),
        checks=checks,
        blockers=[],
        curricula=curricula,
        job_counts=job_counts,
        chunk_counts=chunk_counts,
        path_infos=path_infos,
        vector_counts=vector_counts,
        collection_present=collection_present,
        results=results,
    )


__all__ = [
    "COL_REFERENCE_ALL",
    "DEFAULT_UPLOAD_ROOT",
    "PurgeBlockedError",
    "PurgeError",
    "PurgeExecutionError",
    "PurgeUnreachableError",
    "execute_curriculum_purge",
    "plan_curriculum_purge",
]
