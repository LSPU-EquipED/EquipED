"""Exceptions raised by the feedback module."""

from __future__ import annotations


class EvaluationNotFoundError(Exception):
    """Raised when feedback targets an evaluation_id that doesn't exist."""


class InvalidFeedbackTargetError(Exception):
    """Raised when feedback targets an unknown, mismatched, missing,
    or ambiguous criterion/agent.
    """


__all__ = ["EvaluationNotFoundError", "InvalidFeedbackTargetError"]
