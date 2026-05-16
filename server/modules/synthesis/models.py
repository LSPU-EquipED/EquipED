"""Persistence models for agent outputs and evaluation flags."""

from __future__ import annotations

import uuid
from datetime import datetime

from server.core.database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class AgentResult(Base):
    __tablename__ = "agent_results"

    agent_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evaluation_jobs.evaluation_id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prompt_versions.version_id"), nullable=True
    )
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_seconds: Mapped[float] = mapped_column(nullable=False, default=0.0)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CriterionScore(Base):
    __tablename__ = "criterion_scores"

    criterion_score_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_results.agent_result_id"), nullable=False
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evaluation_jobs.evaluation_id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    criterion_id: Mapped[str] = mapped_column(String(100), nullable=False)
    criterion_title: Mapped[str] = mapped_column(String(300), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvaluationFlag(Base):
    __tablename__ = "evaluation_flags"

    evaluation_flag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evaluation_jobs.evaluation_id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    agent_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_results.agent_result_id"), nullable=False
    )
    criterion_score_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("criterion_scores.criterion_score_id"),
        nullable=False,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_chunks.chunk_id"), nullable=True
    )
    criterion_id: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["AgentResult", "CriterionScore", "EvaluationFlag"]
