"""Dedicated ITSO assessment storage; never fake a legacy AgentResult."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from server.core.database import Base
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    event,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column


class ITSOAssessment(Base):
    __tablename__ = "itso_assessments"
    __table_args__ = (
        CheckConstraint(
            "(scoring_complete = false AND subtotal IS NULL) OR "
            "(scoring_complete = true AND subtotal IS NOT NULL "
            "AND subtotal BETWEEN 1 AND 4)",
            name="ck_itso_assessment_subtotal",
        ),
        CheckConstraint(
            "execution_status IN ('PENDING','RUNNING','COMPLETED','FAILED')",
            name="ck_itso_assessment_execution_status",
        ),
        UniqueConstraint(
            "evaluation_id",
            "contract_version",
            name="uq_itso_assessment_evaluation_contract",
        ),
        Index("ix_itso_assessment_owner_document", "owner_id", "document_id"),
        CheckConstraint("review_revision >= 0", name="ck_itso_review_revision"),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_jobs.evaluation_id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.document_id"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    source_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_source_snapshots.snapshot_id"), nullable=False
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    form_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_form_snapshots.snapshot_id"), nullable=False
    )
    effective_policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    review_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contract_version: Mapped[str] = mapped_column(
        String(80), nullable=False, default="itso_evidence.v1"
    )
    manifest_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    execution_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PENDING"
    )
    scoring_complete: Mapped[bool] = mapped_column(default=False, nullable=False)
    subtotal: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


@event.listens_for(ITSOAssessment, "before_update")
def protect_generated_assessment(_mapper, connection, target):
    table = ITSOAssessment.__table__
    stored = (
        connection.execute(
            select(table).where(table.c.assessment_id == target.assessment_id)
        )
        .mappings()
        .first()
    )
    if stored is not None and stored["result_payload"] is not None:
        for field in (
            "result_payload",
            "evaluation_id",
            "document_id",
            "owner_id",
            "source_snapshot_id",
            "source_hash",
            "form_snapshot_id",
            "effective_policy_hash",
            "execution_status",
            "scoring_complete",
            "subtotal",
            "failure_code",
        ):
            if getattr(target, field) != stored[field]:
                raise ValueError("immutable_generated_assessment")
