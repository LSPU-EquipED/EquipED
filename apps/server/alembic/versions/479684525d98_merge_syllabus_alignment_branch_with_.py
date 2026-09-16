"""merge syllabus-alignment branch with roadmap+advisory chain

Revision ID: 479684525d98
Revises: 20260802_0002, 20260808_0001
Create Date: 2026-08-08 02:33:42.449420

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '479684525d98'
down_revision: Union[str, Sequence[str], None] = ('20260802_0002', '20260808_0001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
