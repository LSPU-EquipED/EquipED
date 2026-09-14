"""Public service facade for syllabus-alignment use cases.

Business rules and persistence live in focused modules; this module preserves a
single stable import surface for HTTP, jobs, and startup callers.
"""

from .commands import create_syllabus_alignment
from .jobs import fail_interrupted_syllabus_alignments, run_syllabus_alignment_job
from .queries import (
    get_current_syllabus_alignment,
    get_syllabus_alignment,
    list_alignment_slms,
)

__all__ = [
    "create_syllabus_alignment",
    "fail_interrupted_syllabus_alignments",
    "get_current_syllabus_alignment",
    "get_syllabus_alignment",
    "list_alignment_slms",
    "run_syllabus_alignment_job",
]
