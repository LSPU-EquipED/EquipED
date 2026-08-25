"""Upload journaling and crash-recovery for document artifacts.

This module owns the no-DB upload ownership markers and the startup
recovery of interrupted or failed uploads. It deliberately does not
import from :mod:`server.modules.documents.service` to avoid a circular
dependency: the service layer calls into this module, never the reverse.
Path constants are consumed from :mod:`server.modules.documents.paths`
so exact filesystem locations are preserved.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from . import paths
from .models import Document

logger = logging.getLogger(__name__)

UNVERIFIED_VECTOR_CLEANUP_WARNING = (
    "Document processing failed and local vector cleanup could not "
    "be verified. Retry deletion when local storage is available."
)


def _create_upload_marker(document_id: uuid.UUID, file_path: Path) -> Path:
    """Durably claim a no-DB upload artifact before opening the PDF."""
    upload_root_existed = paths.UPLOAD_JOURNAL_ROOT.parent.exists()
    journal_existed = paths.UPLOAD_JOURNAL_ROOT.exists()
    paths.UPLOAD_JOURNAL_ROOT.mkdir(parents=True, exist_ok=True)
    if not upload_root_existed:
        _fsync_directory(paths.UPLOAD_JOURNAL_ROOT.parent.parent)
    if not journal_existed:
        _fsync_directory(paths.UPLOAD_JOURNAL_ROOT.parent)

    marker = paths.UPLOAD_JOURNAL_ROOT / f"{document_id}.pending"
    descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as handle:
            handle.write(str(file_path))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    _fsync_directory(paths.UPLOAD_JOURNAL_ROOT)
    return marker


def _fsync_directory(directory: Path) -> None:
    """Persist a directory entry after creating a tracked artifact."""
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remove_upload_marker(marker: Path) -> None:
    """Remove an ownership marker only after its upload has finalized."""
    try:
        marker.unlink(missing_ok=True)
    except OSError:
        logger.warning(
            "Failed to remove no-DB upload ownership marker",
            extra={"marker": str(marker)},
        )


def _cleanup_failed_upload(file_path: Path) -> bool:
    """Remove the uploaded file when preprocessing failed.

    Tries to delete the file up to 3 times (bounded cleanup retries).
    Returns True if deletion succeeds (or file already does not exist),
    and False if deletion fails.
    """
    import time

    for attempt in range(1, 4):
        try:
            if not file_path.exists():
                return True
            file_path.unlink()
            logger.info(
                f"Cleaned up failed upload file (attempt {attempt}/3)",
                extra={"file_path": str(file_path)},
            )
            return True
        except OSError as exc:
            logger.warning(
                f"Failed to clean up failed upload file (attempt {attempt}/3)",
                extra={"file_path": str(file_path), "error": str(exc)},
            )
            if attempt < 3:
                time.sleep(0.05 * attempt)
    return False


def recover_cleanup_pending_documents(db_session_factory: Any) -> int:
    """Recover tracked artifacts left by interrupted or failed uploads.

    If cleanup succeeds, updates their status to FAILED.
    Returns the number of successfully cleaned-up documents.
    """
    session = db_session_factory()
    try:
        docs = (
            session.query(Document)
            .filter(
                Document.processing_status.in_(["PENDING", "CLEANUP_PENDING", "FAILED"])
            )
            .all()
        )
        if not docs:
            return 0

        recovered_count = 0
        for doc in docs:
            warnings = getattr(doc, "processing_warnings", None) or []
            if (
                doc.processing_status == "FAILED"
                and UNVERIFIED_VECTOR_CLEANUP_WARNING in warnings
            ):
                continue

            if not doc.file_path:
                doc.processing_status = "FAILED"
                recovered_count += 1
                continue

            pdf_path = Path(doc.file_path)
            if _cleanup_failed_upload(pdf_path):
                doc.processing_status = "FAILED"
                recovered_count += 1

        if recovered_count > 0:
            session.commit()
            logger.info(
                f"Document cleanup startup recovery successfully cleaned up "
                f"{recovered_count} pending files."
            )
        return recovered_count
    except Exception:
        logger.exception("Failed to recover cleanup-pending documents")
        return 0
    finally:
        session.close()


def recover_no_database_upload_journal() -> int:
    """Remove stale no-DB upload artifacts tracked by ownership markers."""
    if not paths.UPLOAD_JOURNAL_ROOT.exists():
        return 0

    recovered_count = 0
    upload_root = paths.UPLOAD_ROOT.resolve()
    for marker in paths.UPLOAD_JOURNAL_ROOT.glob("*.pending"):
        try:
            file_path = Path(marker.read_text(encoding="utf-8").strip()).resolve()
            if (
                upload_root not in file_path.parents
                or file_path.suffix.lower() != ".pdf"
            ):
                logger.warning(
                    "Ignoring invalid no-DB upload ownership marker",
                    extra={"marker": str(marker)},
                )
                continue
            if _cleanup_failed_upload(file_path):
                _remove_upload_marker(marker)
                recovered_count += 1
        except OSError:
            logger.exception(
                "Failed to recover no-DB upload ownership marker",
                extra={"marker": str(marker)},
            )
    return recovered_count


__all__ = [
    "UNVERIFIED_VECTOR_CLEANUP_WARNING",
    "recover_cleanup_pending_documents",
    "recover_no_database_upload_journal",
]
