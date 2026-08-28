"""SQLAlchemy models for rubric sets, domains, and criteria."""

from __future__ import annotations

import uuid
from datetime import datetime

from server.core.database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class RubricSet(Base):
    __tablename__ = "rubric_sets"
    __table_args__ = (
        UniqueConstraint("agent_id", "version_number", name="uq_rubric_sets_agent_version"),
    )

    rubric_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
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
        Uuid(as_uuid=True), ForeignKey("rubric_domains.rubric_domain_id"), nullable=False
    )
    criterion_code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)


__all__ = ["RubricSet", "RubricDomain", "RubricCriterion"]
