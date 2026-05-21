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


__all__ = ["PromptVersion"]
