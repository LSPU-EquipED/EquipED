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
    UniqueConstraint,
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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
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

    status_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    run_stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    run_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_reported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TrainedAdapter(Base):
    """A trained LoRA adapter uploaded back from a Colab training run."""

    __tablename__ = "trained_adapters"
    __table_args__ = (
        Index("idx_trained_adapters_agent_id", "agent_id"),
        Index("idx_trained_adapters_job_id", "job_id"),
        UniqueConstraint(
            "agent_id", "version", name="uq_trained_adapters_agent_version"
        ),
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
    gguf_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    gguf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gguf_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gguf_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gguf_upload_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    gguf_upload_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    training_summary: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class AgentAdapterPublication(Base):
    """The one adapter version an agent uses for main scoring (none = base)."""

    __tablename__ = "agent_adapter_publication"

    agent_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    adapter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trained_adapters.adapter_id", ondelete="RESTRICT"),
        nullable=False,
    )
    published_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class HostSyncKey(Base):
    """A read-only key the model-server host script uses to pull GGUF files."""

    __tablename__ = "host_sync_keys"

    key_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


__all__ = [
    "AgentAdapterPublication",
    "DpoTrainingJob",
    "HostSyncKey",
    "TrainedAdapter",
]
