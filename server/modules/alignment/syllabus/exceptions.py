"""Exceptions for syllabus alignment operations."""


class SyllabusAlignmentError(Exception):
    """Base error for syllabus alignment operations."""


class SyllabusAlignmentNotFoundError(SyllabusAlignmentError):
    """Raised when an alignment run or owned SLM cannot be found."""


class InvalidSyllabusAlignmentTargetError(SyllabusAlignmentError):
    """Raised when the SLM or syllabus cannot be used for alignment."""


__all__ = [
    "InvalidSyllabusAlignmentTargetError",
    "SyllabusAlignmentError",
    "SyllabusAlignmentNotFoundError",
]
