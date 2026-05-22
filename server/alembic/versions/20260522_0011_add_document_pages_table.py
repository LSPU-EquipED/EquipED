"""add document pages table

Revision ID: 20260522_0011
Revises: 20260522_0010
Create Date: 2026-05-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260522_0011"
down_revision = "20260522_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_pages",
        sa.Column("page_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.document_id"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "is_ocr",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_document_pages_document_id", "document_pages", ["document_id"])
    op.create_index(
        "idx_document_pages_document_page",
        "document_pages",
        ["document_id", "page_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_document_pages_document_page", table_name="document_pages")
    op.drop_index("idx_document_pages_document_id", table_name="document_pages")
    op.drop_table("document_pages")
