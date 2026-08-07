"""Domain exceptions for the curriculum alignment pipeline.

Each exception documents the HTTP status the router lane must map it to;
the router owns that mapping.
"""

from __future__ import annotations


class CourseNotFoundError(Exception):
    """Raised when the requested course does not exist.

    Router maps to 404.
    """


class RoadmapNotFoundError(Exception):
    """Raised when the requested program roadmap does not exist.

    Router maps to 404.
    """


class NoCurriculumMapError(Exception):
    """Raised when a course has zero mapped curriculum objectives.

    Distinguishes "not supported yet" from "0 objectives, all fine" -- the
    caller must never silently report a clean result for an unmapped
    course (design spec section 7). Router maps to 422.
    """


class AlignmentCheckNotFoundError(Exception):
    """Raised when the requested alignment check does not exist.

    Router maps to 404.
    """


class DocumentAccessDeniedError(Exception):
    """Raised when the acting user does not own the target document.

    Mirrors ``documents/service.py``'s owner-only rule for SLMs and other
    non-reference, non-policy document types (see
    ``_is_document_accessible``). Mapped to a 404 (not 403) at the router
    layer to avoid leaking whether the document exists.
    """


class DocumentSourceTypeError(Exception):
    """Raised when the target document is not an SLM.

    Only documents with ``source_type == "slm"`` may be alignment-checked;
    policy/syllabus/curriculum/reference text must never reach the LLM.
    Router maps to 422.
    """


class DocumentNotReadyError(Exception):
    """Raised when the document has not finished Layer-1 ingestion.

    The pipeline reads persisted chunks only, so ``processing_status`` must
    be ``PROCESSED``. Router maps to 409.
    """


class NoUsableDocumentTextError(Exception):
    """Raised when a document has no usable persisted page text.

    Either no usable chunks were persisted, or no complete page fits within
    the alignment prompt budget. Router maps to 409.
    """


class DocumentProgramError(Exception):
    """Raised when the document's program is not the alignment-supported
    program (``BSInfoTech``; ``BSIT`` is only a read alias).

    Router maps to 422.
    """


class CourseProgramMismatchError(Exception):
    """Raised when the course program is unsupported or does not match the
    document program. Router maps to 422.
    """


class CurriculumMapProgramError(Exception):
    """Raised when a mapped objective belongs to a program other than the
    alignment-supported ``BSInfoTech`` (``BSIT`` read alias).

    Router maps to 422.
    """


class AlignmentCheckRateLimitError(Exception):
    """Raised when pacing limits are exceeded for alignment checks."""

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AlignmentCheckCooldownError(Exception):
    """Raised when a user reruns the same alignment check too soon."""

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


__all__ = [
    "CourseNotFoundError",
    "RoadmapNotFoundError",
    "NoCurriculumMapError",
    "AlignmentCheckNotFoundError",
    "DocumentAccessDeniedError",
    "DocumentSourceTypeError",
    "DocumentNotReadyError",
    "NoUsableDocumentTextError",
    "DocumentProgramError",
    "CourseProgramMismatchError",
    "CurriculumMapProgramError",
    "AlignmentCheckRateLimitError",
    "AlignmentCheckCooldownError",
]
