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


class EmptyTrainingDatasetError(TrainingDataError):
    """Raised when no eligible preference pairs exist for a training job."""


class AdapterUploadError(TrainingDataError):
    """Raised when an uploaded adapter file fails size or extension checks."""


class AdapterNotFoundError(TrainingDataError):
    """No trained adapter with that id."""


class AdapterAgentMismatchError(TrainingDataError):
    """The adapter belongs to a different agent."""


class AdapterNotLoadedError(TrainingDataError):
    """The adapter is not loaded on the model server (or that cannot be verified)."""


__all__ = [
    "AdapterNotFoundError",
    "AdapterAgentMismatchError",
    "AdapterNotLoadedError",
    "TrainingDataError",
    "InvalidAgentIdError",
    "TrainingJobNotFoundError",
    "EmptyTrainingDatasetError",
    "AdapterUploadError",
]
