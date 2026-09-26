"""apps/server/modules/training_data/schemas.py"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

AgentId = Literal["sme", "coordinator", "gad", "itso"]


class TrainingJobCreateResponse(BaseModel):
    job_id: uuid.UUID
    agent_id: str
    status: str
    download_url: str
    upload_url: str
    download_expires_at: datetime
    upload_expires_at: datetime
    created_at: datetime


class TrainingJobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    agent_id: str
    status: str
    created_at: datetime
    pair_count: int | None = None
    evaluation_count: int | None = None
    reviewer_count: int | None = None
    pairs_sha256: str | None = None
    export_timestamp: str | None = None

    @classmethod
    def from_job(cls, job: Any) -> TrainingJobListItem:
        manifest = job.manifest_json if isinstance(job.manifest_json, dict) else {}
        return cls(
            job_id=job.job_id,
            agent_id=job.agent_id,
            status=job.status,
            created_at=job.created_at,
            pair_count=manifest.get("pair_count"),
            evaluation_count=manifest.get("evaluation_count"),
            reviewer_count=manifest.get("reviewer_count"),
            pairs_sha256=manifest.get("pairs_sha256"),
            export_timestamp=manifest.get("export_timestamp"),
        )


class TrainingJobListResponse(BaseModel):
    agent_id: str
    jobs: list[TrainingJobListItem]


class TrainingDatasetReadinessResponse(BaseModel):
    agent_id: str
    pair_count: int
    evaluation_count: int
    reviewer_count: int
    skipped_counts: dict[str, int]
    pairs_sha256: str
    export_timestamp: str


class TrainedAdapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    adapter_id: uuid.UUID
    agent_id: str
    job_id: uuid.UUID
    version: int
    file_sha256: str
    size_bytes: int
    created_at: datetime


class TrainedAdapterListResponse(BaseModel):
    agent_id: str
    adapters: list[TrainedAdapterResponse]


__all__ = [
    "AgentId",
    "TrainingJobCreateResponse",
    "TrainingJobListItem",
    "TrainingJobListResponse",
    "TrainingDatasetReadinessResponse",
    "TrainedAdapterResponse",
    "TrainedAdapterListResponse",
]
