"""apps/server/modules/training_data/exceptions.py"""

from __future__ import annotations


class TrainingDataError(Exception):
    """Base exception for the training_data module."""


class InvalidAgentIdError(TrainingDataError):
    """Raised when agent_id is not one of the four known agents."""


class TrainingJobNotFoundError(TrainingDataError):
    """Raised for any token validation failure: missing, expired, used,
    or scoped to a different job. Deliberately undifferentiated so callers
    cannot use error variants to probe for valid tokens/job IDs."""


class AdapterUploadError(TrainingDataError):
    """Raised when an uploaded adapter file fails size or extension checks."""


__all__ = [
    "TrainingDataError",
    "InvalidAgentIdError",
    "TrainingJobNotFoundError",
    "AdapterUploadError",
]
