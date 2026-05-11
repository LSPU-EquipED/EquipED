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

__all__ = [
    "EvaluationsError",
    "EvaluationNotFoundError",
    "ForbiddenEvaluationAccessError",
    "InvalidStatusTransitionError",
    "EvaluationJobStillRunningError",
]
