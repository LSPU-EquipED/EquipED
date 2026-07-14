"""add policy_area to document_chunks, backfill from parent document

Revision ID: 20260713_0005
Revises: 20260713_0004
Create Date: 2026-07-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260713_0005"
down_revision: str | Sequence[str] | None = "20260713_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add policy_area column to document_chunks table
    op.add_column(
        "document_chunks",
        sa.Column("policy_area", sa.String(100), nullable=True),
    )

    # Backfill policy_area for existing policy chunks from their parent document
    op.execute(
        """
        UPDATE document_chunks
        SET policy_area = (
            SELECT documents.policy_area
            FROM documents
            WHERE documents.document_id = document_chunks.document_id
        )
        WHERE document_chunks.source_type = 'policy'
        """
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "policy_area")
