"""Domain exceptions for the curriculum alignment pipeline."""

from __future__ import annotations


class CourseNotFoundError(Exception):
    """Raised when the requested course does not exist."""


class NoCurriculumMapError(Exception):
    """Raised when a course has zero mapped curriculum objectives.

    Distinguishes "not supported yet" from "0 objectives, all fine" -- the
    caller must never silently report a clean result for an unmapped
    course (design spec section 7).
    """


class AlignmentCheckNotFoundError(Exception):
    """Raised when the requested alignment check does not exist."""


__all__ = ["CourseNotFoundError", "NoCurriculumMapError", "AlignmentCheckNotFoundError"]
