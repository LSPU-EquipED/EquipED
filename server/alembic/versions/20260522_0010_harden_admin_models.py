"""harden_admin_models

Revision ID: 20260522_0010
Revises: 20260522_0009
Create Date: 2026-05-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260522_0010"
down_revision: Union[str, None] = "20260522_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "prompt_versions",
        "prompt_text",
        type_=sa.String(10000),
        existing_type=sa.Text(),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_preference_logs_action",
        "preference_logs",
        "action IN ('ACCEPT', 'REJECT', 'EDIT')",
    )
    op.create_index("idx_pref_logs_action", "preference_logs", ["action"])
    op.create_index("idx_pref_logs_created_at", "preference_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_pref_logs_created_at", table_name="preference_logs")
    op.drop_index("idx_pref_logs_action", table_name="preference_logs")
    op.drop_constraint("ck_preference_logs_action", "preference_logs", type_="check")
    op.alter_column(
        "prompt_versions",
        "prompt_text",
        type_=sa.Text(),
        existing_type=sa.String(10000),
        nullable=False,
    )
