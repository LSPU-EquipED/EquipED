"""add_partial_unique_active_prompt

Revision ID: 20260522_0009
Revises: 20260522_0008
Create Date: 2026-05-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260522_0009"
down_revision: Union[str, None] = "20260522_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("idx_prompts_agent_active", table_name="prompt_versions")
    op.create_index(
        "idx_prompts_agent_active_unique",
        "prompt_versions",
        ["agent_id"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
        sqlite_where=sa.text("is_active = 1"),
    )


def downgrade() -> None:
    op.drop_index("idx_prompts_agent_active_unique", table_name="prompt_versions")
    op.create_index("idx_prompts_agent_active", "prompt_versions", ["agent_id", "is_active"])
