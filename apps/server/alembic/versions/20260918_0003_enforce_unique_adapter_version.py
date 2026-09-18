"""enforce unique (agent_id, version) on trained_adapters

Safe migration: deterministically renumbers existing trained_adapters rows per agent_id
in stable (created_at ASC, adapter_id ASC) order starting from 1, preserving all rows,
then applies unique index uq_trained_adapters_agent_version on (agent_id, version).

Revision ID: 20260918_0003
Revises: 20260918_0002
Create Date: 2026-09-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "20260918_0003"
down_revision: str | None = "20260918_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "trained_adapters"
_UNIQUE_INDEX = "uq_trained_adapters_agent_version"
_UNIQUE_COLUMNS = ["agent_id", "version"]


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def _has_index(table: str, name: str) -> bool:
    bind = op.get_bind()
    table_names = inspect(bind).get_table_names()
    if table not in table_names:
        return False
    return name in [i["name"] for i in inspect(bind).get_indexes(table)]


def _renumber_existing_adapters(bind) -> None:
    adapters = sa.table(
        _TABLE_NAME,
        sa.column("adapter_id", sa.String()),
        sa.column("agent_id", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    rows = (
        bind.execute(
            sa.select(
                adapters.c.adapter_id,
                adapters.c.agent_id,
                adapters.c.version,
                adapters.c.created_at,
            ).order_by(
                adapters.c.agent_id.asc(),
                adapters.c.created_at.asc(),
                adapters.c.adapter_id.asc(),
            )
        )
        .mappings()
        .all()
    )

    current_agent = None
    next_ver = 1
    for row in rows:
        agent = row["agent_id"]
        if agent != current_agent:
            current_agent = agent
            next_ver = 1

        target_version = next_ver
        next_ver += 1

        if row["version"] != target_version:
            bind.execute(
                adapters.update()
                .where(adapters.c.adapter_id == row["adapter_id"])
                .values(version=target_version)
            )


def upgrade() -> None:
    if not _has_table(_TABLE_NAME):
        return

    bind = op.get_bind()
    _renumber_existing_adapters(bind)

    if not _has_index(_TABLE_NAME, _UNIQUE_INDEX):
        op.create_index(
            _UNIQUE_INDEX,
            _TABLE_NAME,
            _UNIQUE_COLUMNS,
            unique=True,
        )


def downgrade() -> None:
    if not _has_table(_TABLE_NAME):
        return
    if _has_index(_TABLE_NAME, _UNIQUE_INDEX):
        op.drop_index(_UNIQUE_INDEX, table_name=_TABLE_NAME)
