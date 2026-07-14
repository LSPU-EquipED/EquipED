"""SQLAlchemy models for prompt version management."""

from __future__ import annotations

import uuid
from datetime import datetime

from server.core.database import Base
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column


class PromptVersion(Base):
    """Versioned system prompt used by an evaluator agent."""

    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "version_number",
            name="uq_prompt_versions_agent_version",
        ),
        Index(
            "idx_prompts_agent_active_unique",
            "agent_id",
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_text: Mapped[str] = mapped_column(String(10000), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=True
    )
    motivation: Mapped[str | None] = mapped_column(Text, nullable=True)
    preference_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ModelValidation(Base):
    """Human benchmark score paired with a normal SLM evaluation job."""

    __tablename__ = "model_validations"
    __table_args__ = (
        UniqueConstraint("evaluation_id", name="uq_model_validations_evaluation"),
        Index("idx_model_validations_created_by", "created_by"),
    )

    validation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_jobs.evaluation_id"),
        nullable=False,
    )
    toxicity_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    toxicity_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
    toxicity_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    toxicity_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    toxicity_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    toxicity_assessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ModelValidationCriterionScore(Base):
    """Human benchmark and resulting model score for one agent criterion."""

    __tablename__ = "model_validation_criterion_scores"
    __table_args__ = (
        UniqueConstraint(
            "validation_id",
            "agent_id",
            "criterion_id",
            name="uq_validation_agent_criterion",
        ),
        Index("idx_validation_criterion_validation", "validation_id"),
    )

    expected_score_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    validation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("model_validations.validation_id"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    criterion_id: Mapped[str] = mapped_column(String(100), nullable=False)
    criterion_title: Mapped[str] = mapped_column(String(300), nullable=False)
    expected_score: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    absolute_error: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["ModelValidation", "ModelValidationCriterionScore", "PromptVersion"]
