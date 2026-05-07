"""create documents and document_chunks tables

Revision ID: 20260507_0001
Revises:
Create Date: 2026-05-07 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260507_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("document_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("program", sa.String(length=300), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column(
            "has_ocr_pages",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "processing_status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
    )

    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.document_id"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("agent_domain", sa.String(length=50), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("is_ocr", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "chroma_stored",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("idx_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("idx_chunks_agent_domain", "document_chunks", ["agent_domain"])


def downgrade() -> None:
    op.drop_index("idx_chunks_agent_domain", table_name="document_chunks")
    op.drop_index("idx_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_table("documents")
