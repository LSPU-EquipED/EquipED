"""Domain exceptions for rubrics module."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .contracts import ValidationReport


class RubricsError(Exception):
    """Base exception for rubrics domain."""


class RubricConflictError(RubricsError):
    """Raised when attempting to mutate an immutable rubric set or on state conflict."""


class RubricNotFoundError(RubricsError, LookupError):
    """Raised when a rubric entity is not found."""


class RubricValidationError(RubricsError, ValueError):
    """Raised when rubric capability manifest or structure validation fails."""

    def __init__(self, message: str, report: ValidationReport | None = None) -> None:
        super().__init__(message)
        self.report = report


__all__ = [
    "RubricConflictError",
    "RubricNotFoundError",
    "RubricValidationError",
    "RubricsError",
]
