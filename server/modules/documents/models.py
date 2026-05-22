"""SQLAlchemy models for documents layer-1 data."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from server.core.database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class Document(Base):
    """Uploaded source document metadata."""

    __tablename__ = "documents"

    document_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    course_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lesson_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    program: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_ocr_pages: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_status: Mapped[str] = mapped_column(String(50), default="PENDING")
    structured_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_outline: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    section_summaries: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    key_facts: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    processing_warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    evaluation_readiness: Mapped[str] = mapped_column(String(50), default="PENDING")


class DocumentChunk(Base):
    """Persisted semantic chunk produced by ingestion."""

    __tablename__ = "document_chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.document_id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_domain: Mapped[str] = mapped_column(String(50), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    chroma_stored: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )


class DocumentPage(Base):
    """Persisted extracted page text for frontend flagging."""

    __tablename__ = "document_pages"

    page_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.document_id"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )


__all__ = ["Base", "Document", "DocumentChunk", "DocumentPage"]
