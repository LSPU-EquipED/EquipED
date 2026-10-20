"""Stored historical verification runs, tasks and HTTP attempts."""

import uuid

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from server.core.database import Base


class VerificationRun(Base):
    __tablename__ = "itso_verification_runs"
    __table_args__ = (
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= reservation AND reservation <= 95",
            name="ck_itso_tool_global_budget",
        ),
    )
    plan_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itso_assessments.assessment_id"), nullable=False
    )
    plan_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    reservation: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class VerificationTask(Base):
    __tablename__ = "itso_verification_tasks"
    __table_args__ = (
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= reservation AND reservation <= 5",
            name="ck_itso_tool_lane_budget",
        ),
    )
    plan_hash: Mapped[str] = mapped_column(
        ForeignKey("itso_verification_runs.plan_hash"), primary_key=True
    )
    task_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    started: Mapped[bool] = mapped_column(nullable=False, default=False)
    reservation: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capture_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ToolAttempt(Base):
    __tablename__ = "itso_tool_attempts"
    __table_args__ = (
        UniqueConstraint(
            "plan_hash", "task_id", "ordinal", name="uq_itso_tool_attempt_ordinal"
        ),
        ForeignKeyConstraint(
            ["plan_hash", "task_id"],
            ["itso_verification_tasks.plan_hash", "itso_verification_tasks.task_id"],
            name="fk_itso_attempt_task",
        ),
        CheckConstraint("ordinal BETWEEN 1 AND 5", name="ck_itso_attempt_ordinal"),
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    plan_hash: Mapped[str] = mapped_column(
        ForeignKey("itso_verification_runs.plan_hash"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(String(80), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    request_class: Mapped[str] = mapped_column(String(30), nullable=False)
    destination_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    started_monotonic: Mapped[float] = mapped_column(Float, nullable=False)
    elapsed: Mapped[float | None] = mapped_column(Float, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    completed: Mapped[bool] = mapped_column(nullable=False, default=False)
