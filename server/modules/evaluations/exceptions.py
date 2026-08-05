"""
Module-local exceptions for evaluations job lifecycle operations.
"""

class EvaluationsError(Exception):
    """Base error for evaluations module operations."""

class EvaluationNotFoundError(EvaluationsError):
    """Raised when the evaluation job id does not exist."""

class ForbiddenEvaluationAccessError(EvaluationsError):
    """Raised when a user tries to access a job they do not own."""

class InvalidStatusTransitionError(EvaluationsError):
    """Raised when a status move is not allowed given the current state."""

class EvaluationJobStillRunningError(EvaluationsError):
    """Raised if client requests final results before job is complete."""


class EvaluationPipelineUnavailableError(EvaluationsError):
    """Raised when the evaluation pipeline is not ready to accept work."""


class InvalidEvaluationTargetError(EvaluationsError):
    """Raised when the target document is not eligible for evaluation."""


class EvaluationExecutionOwnershipError(EvaluationsError):
    """Raised when a status transition lacks a valid execution token."""


class SyllabusAlignmentNotFoundError(EvaluationsError):
    """Raised when an alignment run or owned SLM cannot be found."""


class InvalidSyllabusAlignmentTargetError(EvaluationsError):
    """Raised when the SLM or syllabus cannot be used for alignment."""


__all__ = [
    "EvaluationsError",
    "EvaluationNotFoundError",
    "ForbiddenEvaluationAccessError",
    "InvalidStatusTransitionError",
    "EvaluationJobStillRunningError",
    "EvaluationPipelineUnavailableError",
    "InvalidEvaluationTargetError",
    "EvaluationExecutionOwnershipError",
    "InvalidSyllabusAlignmentTargetError",
    "SyllabusAlignmentNotFoundError",
]
