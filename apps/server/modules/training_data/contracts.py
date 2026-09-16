"""DPO contracts and data structures."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True, slots=True)
class DpoPair:
    """A single DPO preference pair ready for fine-tuning."""

    pair_id: str
    prompt: str
    chosen: str
    rejected: str
    generation_id: uuid.UUID
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    agent_id: str
    model_name: str
    reviewer_ids: frozenset[uuid.UUID]


class DpoPackageManifest(BaseModel):
    """Manifest describing an exported DPO training package."""

    model_config = ConfigDict(frozen=True)

    manifest_version: str = "equiped.dpo-package.v1"
    agent_id: str
    model_name: str | None = None
    response_contract_keys: list[str] = Field(default_factory=list)
    pair_count: int = 0
    evaluation_count: int = 0
    reviewer_count: int = 0
    skipped_counts: dict[str, int] = Field(default_factory=dict)
    pairs_sha256: str
    pairs_bytes: int
    provenance_sha256: str
    provenance_bytes: int
    export_timestamp: str


__all__ = [
    "DpoPackageManifest",
    "DpoPair",
]
