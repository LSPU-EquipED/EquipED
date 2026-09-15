"""compatibility shim for dev DB already at 20260713_0004

This empty revision restores the missing 20260713_0004 revision so Alembic
can resolve the current dev database state without recreating the deferred
Crossref tables that the original 0004 contained.

Revision ID: 20260713_0004
Revises: 20260713_0002
Create Date: 2026-07-13

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260713_0004"
down_revision: str | Sequence[str] | None = "20260713_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op — dev DB is already past this point."""
    pass


def downgrade() -> None:
    """No-op — this revision exists only for compatibility."""
    pass
