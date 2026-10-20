"""Public service facade for syllabus-alignment use cases.

Business rules and persistence live in focused modules; this module preserves a
single stable import surface for HTTP, jobs, and startup callers.
"""

from __future__ import annotations

import uuid
from typing import Any

from .commands import create_syllabus_alignment
from .jobs import fail_interrupted_syllabus_alignments, run_syllabus_alignment_job
from .queries import (
    get_current_syllabus_alignment,
    get_syllabus_alignment,
)
from .queries import (
    list_alignment_slms as _list_alignment_slms,
)
from .schemas import SyllabusAlignmentSlmListResponse


def list_alignment_slms(
    db: Any,
    *,
    requested_by: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    status_filter: str | None = None,
) -> SyllabusAlignmentSlmListResponse:
    return _list_alignment_slms(
        db,
        requested_by=requested_by,
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status_filter,
    )


__all__ = [
    "create_syllabus_alignment",
    "fail_interrupted_syllabus_alignments",
    "get_current_syllabus_alignment",
    "get_syllabus_alignment",
    "list_alignment_slms",
    "run_syllabus_alignment_job",
]
