"""apps/server/modules/training_data/schemas.py"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

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


class TrainingJobListResponse(BaseModel):
    agent_id: str
    jobs: list[TrainingJobListItem]


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
    "TrainedAdapterResponse",
    "TrainedAdapterListResponse",
]
