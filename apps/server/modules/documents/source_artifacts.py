"""Immutable source artifacts retained for historical ITSO assessments."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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

from server.core.database import Base


class DocumentSourceSnapshot(Base):
    __tablename__ = "document_source_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "source_hash",
            "extractor_version",
            name="uq_source_snapshot_identity",
        ),
        Index("ix_source_snapshot_document", "document_id"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)
    canonicalization_version: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_map: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    reference_inventory: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    inventory_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    inventory_version: Mapped[str] = mapped_column(String(100), nullable=False)
    inventory_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    inventory_uncertainties: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class DocumentSourcePreparation(Base):
    __tablename__ = "document_source_preparations"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING','RUNNING','READY','FAILED')",
            name="ck_source_preparation_state",
        ),
        CheckConstraint(
            "attempt_count BETWEEN 0 AND 2", name="ck_source_preparation_attempts"
        ),
        UniqueConstraint(
            "document_id",
            "source_hash",
            "extractor_version",
            name="uq_source_preparation_identity",
        ),
        Index("ix_source_preparation_state", "state"),
    )

    preparation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claim_token: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


__all__ = ["DocumentSourceSnapshot", "DocumentSourcePreparation"]
