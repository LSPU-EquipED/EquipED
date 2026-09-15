"""SQLAlchemy models for dynamic CID evaluation forms."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from server.core.database import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column


class RubricSet(Base):
    __tablename__ = "rubric_sets"
    __table_args__ = (
        UniqueConstraint(
            "agent_id", "version_number", name="uq_rubric_sets_agent_version"
        ),
        UniqueConstraint(
            "agent_id", "rubric_set_id", name="uq_rubric_sets_agent_id_rubric_set_id"
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_rubric_sets_status",
        ),
        Index(
            "uq_rubric_sets_one_draft_per_agent",
            "agent_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
    )

    rubric_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    adapter_key: Mapped[str] = mapped_column(String(50), nullable=False)
    adapter_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retired_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RubricDomain(Base):
    __tablename__ = "rubric_domains"
    __table_args__ = (
        UniqueConstraint("rubric_set_id", "code", name="uq_rubric_domains_set_code"),
    )

    rubric_domain_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rubric_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rubric_sets.rubric_set_id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)


class RubricCriterion(Base):
    __tablename__ = "rubric_criteria"
    __table_args__ = (
        UniqueConstraint(
            "rubric_domain_id", "criterion_code", name="uq_rubric_criteria_domain_code"
        ),
    )

    rubric_criterion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rubric_domain_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rubric_domains.rubric_domain_id"),
        nullable=False,
    )
    criterion_code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    strategy_config: Mapped[dict[str, Any] | None] = mapped_column(
        sa.JSON, nullable=True
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)


class RubricAgentActivation(Base):
    __tablename__ = "rubric_agent_activations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["agent_id", "rubric_set_id"],
            ["rubric_sets.agent_id", "rubric_sets.rubric_set_id"],
            name="fk_rubric_agent_activations_rubric_set",
        ),
    )

    agent_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    rubric_set_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EvaluationFormSnapshot(Base):
    __tablename__ = "evaluation_form_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_id", "agent_id", name="uq_evaluation_form_snapshots_eval_agent"
        ),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evaluation_jobs.evaluation_id"), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    rubric_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rubric_sets.rubric_set_id"), nullable=False
    )
    snapshot_payload: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(50), nullable=False)
    adapter_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = [
    "EvaluationFormSnapshot",
    "RubricAgentActivation",
    "RubricCriterion",
    "RubricDomain",
    "RubricSet",
]
