"""correct ITSO agent prompt directive to canonical office name

Revision ID: 20260918_0001
Revises: 20260917_0001
Create Date: 2026-09-18

Safe, additive data-only migration to update persisted active ITSO prompt directives
from 'IT Security Officer (ITSO)' to 'Innovation and Technology Support Office (ITSO)'
without modifying schema or altering historical non-prompt records.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "20260918_0001"
down_revision: str | None = "20260917_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_DIRECTIVE_PREFIX = "IT Security Officer (ITSO)"
CANONICAL_DIRECTIVE_PREFIX = "Innovation and Technology Support Office (ITSO)"


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    if not _has_table("prompt_versions"):
        return

    bind = op.get_bind()

    # Query active ITSO prompt rows containing the legacy title
    rows = (
        bind.execute(
            sa.text(
                "SELECT version_id, prompt_text FROM prompt_versions "
                "WHERE agent_id = :agent_id AND is_active = :active"
            ),
            {"agent_id": "itso", "active": True},
        )
        .mappings()
        .all()
    )

    for row in rows:
        text_val: str = row["prompt_text"]
        if OLD_DIRECTIVE_PREFIX in text_val:
            updated_text = text_val.replace(
                OLD_DIRECTIVE_PREFIX, CANONICAL_DIRECTIVE_PREFIX
            )
            bind.execute(
                sa.text(
                    "UPDATE prompt_versions SET prompt_text = :new_text "
                    "WHERE version_id = :vid"
                ),
                {"new_text": updated_text, "vid": row["version_id"]},
            )


def downgrade() -> None:
    if not _has_table("prompt_versions"):
        return

    bind = op.get_bind()

    # Query active ITSO prompt rows containing the canonical title to restore old label
    rows = (
        bind.execute(
            sa.text(
                "SELECT version_id, prompt_text FROM prompt_versions "
                "WHERE agent_id = :agent_id AND is_active = :active"
            ),
            {"agent_id": "itso", "active": True},
        )
        .mappings()
        .all()
    )

    for row in rows:
        text_val: str = row["prompt_text"]
        if CANONICAL_DIRECTIVE_PREFIX in text_val:
            restored_text = text_val.replace(
                CANONICAL_DIRECTIVE_PREFIX, OLD_DIRECTIVE_PREFIX
            )
            bind.execute(
                sa.text(
                    "UPDATE prompt_versions SET prompt_text = :new_text "
                    "WHERE version_id = :vid"
                ),
                {"new_text": restored_text, "vid": row["version_id"]},
            )
