"""
Module-local exceptions for synthesis read/query operations.

These are domain errors raised by the service layer. The router is
responsible for mapping them to HTTP responses; no HTTP concerns leak
into the service layer.
"""

from __future__ import annotations


class SynthesisError(Exception):
    """Base error for synthesis module operations."""


class EvaluationResultsNotFoundError(SynthesisError):
    """Raised when evaluation results are not accessible to the requester."""


class UnsupportedProgramFilterError(SynthesisError):
    """Raised when a matrix program filter is not a supported program."""


__all__ = [
    "SynthesisError",
    "EvaluationResultsNotFoundError",
    "UnsupportedProgramFilterError",
]
