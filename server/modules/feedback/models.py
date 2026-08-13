"""Persistence models for human preference/feedback logs."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from server.core.database import Base


class PreferenceLog(Base):
    __tablename__ = "preference_logs"
    __table_args__ = (
        CheckConstraint(
            sa.column("action").in_(["ACCEPT", "REJECT", "EDIT"]),
            name="ck_preference_logs_action",
        ),
        Index("idx_pref_logs_action", "action"),
        Index("idx_pref_logs_created_at", sa.text("created_at DESC")),
    )

    log_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_jobs.evaluation_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    agent_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    criterion_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    edited_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


__all__ = ["PreferenceLog"]
