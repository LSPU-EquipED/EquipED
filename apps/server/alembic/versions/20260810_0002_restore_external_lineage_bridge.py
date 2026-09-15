"""Restore the externally applied 20260810 migration lineage.

The schema effects represented by 20260808_0002 were already applied to the
shared database when this revision was stamped.  This bridge is intentionally
empty: it records that external lineage without replaying any DDL.
"""

from collections.abc import Sequence

revision = "20260810_0002"
down_revision = "20260808_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Record externally applied lineage; no schema operation is required."""


def downgrade() -> None:
    """Remove only the lineage marker; never alter schema state."""
