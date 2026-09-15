"""Public service facade for curriculum-alignment use cases.

Business rules and persistence live in focused modules; this module preserves a
single stable import surface for HTTP and external callers.
"""

from .admission import require_owned_document
from .queries import (
    get_alignment_check,
    get_coverage_metadata,
    get_document_pages_for_check,
    list_alignment_checks,
    to_alignment_check_response,
)
from .repository import delete_alignment_check
from .workflow import run_curriculum_alignment_check

__all__ = [
    "delete_alignment_check",
    "get_alignment_check",
    "get_coverage_metadata",
    "get_document_pages_for_check",
    "list_alignment_checks",
    "require_owned_document",
    "run_curriculum_alignment_check",
    "to_alignment_check_response",
]
