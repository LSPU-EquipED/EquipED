from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from server.core.database import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column


class DpoTrainingJob(Base):
    """A frozen DPO dataset export paired with two job-scoped credentials.

    The dataset snapshot (pairs/provenance/manifest content) is captured at
    job-creation time so the download endpoint always returns exactly what
    was frozen then, even if new corrections land afterward.
    """

    __tablename__ = "dpo_training_jobs"
    __table_args__ = (
        CheckConstraint(
            sa.column("status").in_(["pending", "downloaded", "completed"]),
            name="ck_dpo_training_jobs_status",
        ),
        Index("idx_dpo_training_jobs_agent_id", "agent_id"),
        Index("idx_dpo_training_jobs_created_at", sa.text("created_at DESC")),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    pairs_content: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_content: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False)

    download_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    download_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    download_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    upload_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    upload_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    upload_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TrainedAdapter(Base):
    """A trained LoRA adapter uploaded back from a Colab training run."""

    __tablename__ = "trained_adapters"
    __table_args__ = (
        Index("idx_trained_adapters_agent_id", "agent_id"),
        Index("idx_trained_adapters_job_id", "job_id"),
    )

    adapter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("dpo_training_jobs.job_id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


__all__ = ["DpoTrainingJob", "TrainedAdapter"]
