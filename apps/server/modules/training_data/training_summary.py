"""Validation of the optional training summary an adapter archive carries."""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

logger = logging.getLogger(__name__)

_BOUND = 1_000_000.0

Metric = Annotated[
    float, Field(strict=True, allow_inf_nan=False, ge=-_BOUND, le=_BOUND)
]
Count = Annotated[int, Field(strict=True, ge=0, le=10_000_000)]


class _Summary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @field_validator("*", mode="before")
    @classmethod
    def _reject_bool(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("booleans are not numbers")
        return value


class TrainingSnapshot(_Summary):
    step: Count | None = None
    loss: Metric | None = None
    margin: Metric | None = None
    accuracy: Metric | None = None
    chosen: Metric | None = None
    rejected: Metric | None = None


class HeldoutSummary(_Summary):
    pair_count: Count | None = None
    loss: Metric | None = None
    margin: Metric | None = None
    accuracy: Metric | None = None


class TrainingSummary(_Summary):
    version: Literal[1] = 1
    steps: Count | None = None
    epochs: Metric | None = None
    first: TrainingSnapshot | None = None
    last: TrainingSnapshot | None = None
    heldout: HeldoutSummary | None = None


def extract_training_summary(raw: Any) -> dict[str, Any] | None:
    """Return a clean summary dict, or None when it is absent or invalid.

    Never raises: a bad summary must not cost anyone a finished training run.
    """
    if raw is None:
        return None
    try:
        summary = TrainingSummary.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "Ignoring invalid training_summary in adapter archive "
            "(%d validation error(s))",
            exc.error_count(),
        )
        return None
    cleaned = summary.model_dump(mode="json", exclude_none=True)
    for key in ("first", "last", "heldout"):
        if cleaned.get(key) == {}:
            del cleaned[key]
    # Only {"version": 1} (or nothing else of value) means there is nothing to show.
    if not any(key in cleaned for key in ("steps", "first", "last", "heldout")):
        return None
    return cleaned


__all__ = [
    "HeldoutSummary",
    "TrainingSnapshot",
    "TrainingSummary",
    "extract_training_summary",
]
