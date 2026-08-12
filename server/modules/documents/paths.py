"""Central ownership of repository-root document upload paths.

Single source of truth for ``<repo>/uploads`` and
``<repo>/uploads/.upload-journal``. Both the documents service and the
upload journaling module resolve these paths from here (consuming
:data:`UPLOAD_ROOT` / :data:`UPLOAD_JOURNAL_ROOT` explicitly), so tests
override a single module instead of stale per-consumer aliases.
"""

from __future__ import annotations

from pathlib import Path

from .exceptions import DocumentsError

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_ROOT = _PROJECT_ROOT / "uploads"
UPLOAD_JOURNAL_ROOT = UPLOAD_ROOT / ".upload-journal"


def resolve_document_pdf_path(value: str | Path | None) -> Path:
    """Return a validated, repository-owned uploaded PDF path.

    Deliberately exposes only a generic error so callers cannot turn path
    validation into a filesystem disclosure primitive.
    """
    invalid = DocumentsError("invalid document source")
    if value is None or not str(value).strip():
        raise invalid
    try:
        candidate = Path(value)
        root = UPLOAD_ROOT.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise invalid
        if resolved.suffix.lower() != ".pdf":
            raise invalid
        return resolved
    except (OSError, RuntimeError, TypeError, ValueError):
        raise invalid from None


__all__ = [
    "UPLOAD_ROOT",
    "UPLOAD_JOURNAL_ROOT",
    "resolve_document_pdf_path",
]
