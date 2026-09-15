"""add CHECK constraint enforcing valid policy_area

Revision ID: 20260713_0002
Revises: 20260713_0001
Create Date: 2026-07-13

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260713_0002"
down_revision: str | Sequence[str] | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "ck_policy_area_valid"


def upgrade() -> None:
    op.create_check_constraint(
        CONSTRAINT_NAME,
        "documents",
        """(source_type != 'policy' AND policy_area IS NULL)
            OR (source_type = 'policy' AND policy_area IS NOT NULL AND policy_area IN
                ('intellectual_property', 'data_privacy',
                 'academic_rights', 'general_itso'))""",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "documents", type_="check")
