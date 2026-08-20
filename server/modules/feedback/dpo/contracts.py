"""Contracts for DPO training pair projection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DpoPair:
    """One evaluation's DPO training pair: full-response chosen vs. rejected."""

    prompt: str
    chosen: str
    rejected: str
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    reviewer_ids: frozenset[uuid.UUID]
