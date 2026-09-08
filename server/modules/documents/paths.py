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
        raw_val = str(value)
        root = UPLOAD_ROOT.resolve(strict=True)

        # 1. Direct candidate
        candidate = Path(raw_val)
        if candidate.is_absolute():
            try:
                resolved = candidate.resolve(strict=True)
                if (
                    resolved.is_relative_to(root)
                    and resolved.is_file()
                    and resolved.suffix.lower() == ".pdf"
                ):
                    return resolved
            except (OSError, RuntimeError):
                pass

        # 2. Extract standard filename (handles R2 URI, Windows path, macOS path)
        from server.core.storage import extract_document_filename, get_storage_backend

        filename = extract_document_filename(raw_val)
        if filename and filename.lower().endswith(".pdf"):
            local_target = (root / filename).resolve()
            if (
                local_target.is_relative_to(root)
                and local_target.is_file()
                and local_target.suffix.lower() == ".pdf"
            ):
                return local_target

            # 3. Pull from storage backend if available
            try:
                storage = get_storage_backend()
                if storage.file_exists(raw_val) or storage.file_exists(filename):
                    storage.download_file(raw_val, local_target)
                    resolved_target = local_target.resolve()
                    if (
                        resolved_target.is_relative_to(root)
                        and resolved_target.is_file()
                        and resolved_target.suffix.lower() == ".pdf"
                    ):
                        return resolved_target
            except Exception:
                pass

        raise invalid
    except DocumentsError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError):
        raise invalid from None


__all__ = [
    "UPLOAD_ROOT",
    "UPLOAD_JOURNAL_ROOT",
    "resolve_document_pdf_path",
]
