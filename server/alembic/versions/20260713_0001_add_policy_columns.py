"""add policy_area to documents, section_ref/chunk_index to document_chunks

Revision ID: 20260713_0001
Revises: 20260712_0001
Create Date: 2026-07-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260713_0001"
down_revision: str | Sequence[str] | None = "20260712_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add policy_area column to documents table
    op.add_column(
        "documents",
        sa.Column("policy_area", sa.String(100), nullable=True),
    )

    # Add section_ref column to document_chunks table
    op.add_column(
        "document_chunks",
        sa.Column("section_ref", sa.String(200), nullable=True),
    )

    # Add chunk_index column to document_chunks table
    op.add_column(
        "document_chunks",
        sa.Column("chunk_index", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "chunk_index")
    op.drop_column("document_chunks", "section_ref")
    op.drop_column("documents", "policy_area")
