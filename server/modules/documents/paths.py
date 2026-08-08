"""Central ownership of repository-root document upload paths.

Single source of truth for ``<repo>/uploads`` and
``<repo>/uploads/.upload-journal``. Both the documents service and the
upload journaling module resolve these paths from here (consuming
:data:`UPLOAD_ROOT` / :data:`UPLOAD_JOURNAL_ROOT` explicitly), so tests
override a single module instead of stale per-consumer aliases.
"""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_ROOT = _PROJECT_ROOT / "uploads"
UPLOAD_JOURNAL_ROOT = UPLOAD_ROOT / ".upload-journal"

__all__ = [
    "UPLOAD_ROOT",
    "UPLOAD_JOURNAL_ROOT",
]
