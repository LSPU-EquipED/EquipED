"""Add user_documents association table for personal storage ownership.

Revision ID: 20260911_0001
Revises: 20260910_0001
Create Date: 2026-09-11 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260911_0001"
down_revision: str | None = "20260910_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_documents",
        sa.Column("user_document_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.document_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id", "document_id", name="uq_user_documents_user_doc"
        ),
    )

    # Backfill user storage associations from existing uploads
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            INSERT INTO user_documents (
                user_document_id, user_id, document_id, created_at
            )
            SELECT
                gen_random_uuid(),
                uploaded_by,
                document_id,
                COALESCE(uploaded_at, NOW())
            FROM documents
            WHERE uploaded_by IS NOT NULL
            ON CONFLICT (user_id, document_id) DO NOTHING
            """
        )
    else:
        # SQLite or other dialect fallback
        op.execute(
            """
            INSERT OR IGNORE INTO user_documents (
                user_document_id, user_id, document_id, created_at
            )
            SELECT document_id, uploaded_by, document_id, CURRENT_TIMESTAMP
            FROM documents
            WHERE uploaded_by IS NOT NULL
            """
        )


def downgrade() -> None:
    op.drop_table("user_documents")
