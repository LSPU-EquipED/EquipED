"""apps/server/modules/training_data/schemas.py"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from server.modules.training_data.training_summary import TrainingSummary

AgentId = Literal["sme", "coordinator", "gad", "itso"]

RunStage = Literal[
    "starting",
    "training",
    "sending_model",
    "converting",
    "sending_file",
    "finished",
    "failed",
]


class RunStatusRequest(BaseModel):
    stage: RunStage
    step: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=1)
    message: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _step_within_total(self) -> RunStatusRequest:
        if self.step is not None and self.total is not None and self.step > self.total:
            raise ValueError("step cannot be greater than total")
        return self


class TrainingJobCreateResponse(BaseModel):
    job_id: uuid.UUID
    agent_id: str
    status: str
    download_url: str
    upload_url: str
    download_expires_at: datetime
    upload_expires_at: datetime
    created_at: datetime
    notebook: str | None = None
    notebook_filename: str | None = None


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
    run_stage: str | None = None
    run_step: int | None = None
    run_total: int | None = None
    run_message: str | None = None
    run_reported_at: datetime | None = None
    seconds_since_report: int | None = None

    @classmethod
    def from_job(cls, job: Any) -> TrainingJobListItem:
        manifest = job.manifest_json if isinstance(job.manifest_json, dict) else {}
        reported = getattr(job, "run_reported_at", None)
        seconds_since: int | None = None
        if reported is not None:
            if reported.tzinfo is None:
                reported = reported.replace(tzinfo=UTC)
            seconds_since = max(0, int((datetime.now(UTC) - reported).total_seconds()))
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
            run_stage=getattr(job, "run_stage", None),
            run_step=getattr(job, "run_step", None),
            run_total=getattr(job, "run_total", None),
            run_message=getattr(job, "run_message", None),
            run_reported_at=reported,
            seconds_since_report=seconds_since,
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


class AdapterGgufInfo(BaseModel):
    size_bytes: int
    sha256: str
    uploaded_at: datetime


def adapter_gguf_info(adapter: Any) -> AdapterGgufInfo | None:
    """Metadata of the stored GGUF, or None unless every field is present."""
    if (
        adapter.gguf_storage_key is None
        or adapter.gguf_sha256 is None
        or adapter.gguf_size_bytes is None
        or adapter.gguf_uploaded_at is None
    ):
        return None
    return AdapterGgufInfo(
        size_bytes=adapter.gguf_size_bytes,
        sha256=adapter.gguf_sha256,
        uploaded_at=adapter.gguf_uploaded_at,
    )


class TrainedAdapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    adapter_id: uuid.UUID
    agent_id: str
    job_id: uuid.UUID
    version: int
    file_sha256: str
    size_bytes: int
    created_at: datetime
    training_summary: TrainingSummary | None = None
    gguf: AdapterGgufInfo | None = None


class TrainedAdapterUploadResponse(TrainedAdapterResponse):
    gguf_upload_url: str | None = None


class GgufDownloadLinkResponse(BaseModel):
    url: str
    filename: str
    sha256: str
    size_bytes: int
    expires_at: datetime


class TrainedAdapterListItem(TrainedAdapterResponse):
    gguf_filename: str
    loaded: bool | None
    published: bool


class TrainedAdapterListResponse(BaseModel):
    agent_id: str
    adapters: list[TrainedAdapterListItem]
    published_adapter_id: uuid.UUID | None = None
    server_reachable: bool = True
    unrecognized_server_adapters: list[str] = []


class PublishAdapterRequest(BaseModel):
    adapter_id: uuid.UUID


class HostStateResponse(BaseModel):
    has_active_key: bool
    created_at: datetime | None = None
    last_seen_at: datetime | None = None


class HostKeyCreatedResponse(BaseModel):
    key: str
    created_at: datetime


class HostManifestEntry(BaseModel):
    adapter_id: uuid.UUID
    agent_id: str
    version: int
    filename: str
    sha256: str
    size_bytes: int
    published: bool


class HostManifestResponse(BaseModel):
    adapters: list[HostManifestEntry]


__all__ = [
    "AgentId",
    "TrainingJobCreateResponse",
    "TrainingJobListItem",
    "TrainingJobListResponse",
    "TrainingDatasetReadinessResponse",
    "AdapterGgufInfo",
    "adapter_gguf_info",
    "GgufDownloadLinkResponse",
    "TrainedAdapterResponse",
    "TrainedAdapterUploadResponse",
    "TrainedAdapterListItem",
    "TrainedAdapterListResponse",
    "PublishAdapterRequest",
    "HostStateResponse",
    "HostKeyCreatedResponse",
    "HostManifestEntry",
    "HostManifestResponse",
]
