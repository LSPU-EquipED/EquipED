"""Exceptions raised by the feedback module."""

from __future__ import annotations


class EvaluationNotFoundError(Exception):
    """Raised when feedback targets an evaluation_id that doesn't exist."""


__all__ = ["EvaluationNotFoundError"]
