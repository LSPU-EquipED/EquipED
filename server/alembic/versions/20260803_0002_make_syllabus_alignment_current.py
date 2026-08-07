"""retain one current syllabus alignment result per SLM

Repair note (2026-08-08): the shared dev DB was never stamped through this
migration, so the old unique index may or may not exist depending on the
target database. Upgrade/downgrade are conditional: the row-dedup runs only
when the table exists, and index operations only when the target state
differs.

Revision ID: 20260803_0002
Revises: 20260803_0001
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260803_0002"
down_revision = "20260803_0001"
branch_labels = None
depends_on = None

_TABLE_NAME = "syllabus_alignment_runs"
_OLD_INDEX = "uq_syllabus_alignment_active_slm"
_NEW_INDEX = "uq_syllabus_alignment_slm"


def _has_table() -> bool:
    bind = op.get_bind()
    return _TABLE_NAME in inspect(bind).get_table_names()


def _has_index(name: str) -> bool:
    bind = op.get_bind()
    return name in [i["name"] for i in inspect(bind).get_indexes(_TABLE_NAME)]


def _obsolete_alignment_ids(rows: list[dict[str, object]]) -> list[object]:
    retained_slms: set[object] = set()
    obsolete_ids: list[object] = []
    for row in rows:
        if row["slm_document_id"] in retained_slms:
            obsolete_ids.append(row["alignment_id"])
        else:
            retained_slms.add(row["slm_document_id"])
    return obsolete_ids


def upgrade() -> None:
    if _has_table():
        bind = op.get_bind()
        runs = sa.table(
            "syllabus_alignment_runs",
            sa.column("alignment_id", sa.Uuid()),
            sa.column("slm_document_id", sa.Uuid()),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        rows = list(bind.execute(
            sa.select(
                runs.c.alignment_id,
                runs.c.slm_document_id,
                runs.c.created_at,
            ).order_by(
                runs.c.slm_document_id,
                runs.c.created_at.desc(),
                runs.c.alignment_id.desc(),
            )
        ).mappings())
        obsolete_ids = _obsolete_alignment_ids(rows)
        if obsolete_ids:
            bind.execute(
                runs.delete().where(runs.c.alignment_id.in_(obsolete_ids))
            )

    if _has_index(_OLD_INDEX):
        op.drop_index(
            _OLD_INDEX,
            table_name=_TABLE_NAME,
        )
    if not _has_index(_NEW_INDEX):
        op.create_index(
            _NEW_INDEX,
            "syllabus_alignment_runs",
            ["slm_document_id"],
            unique=True,
        )


def downgrade() -> None:
    if _has_index(_NEW_INDEX):
        op.drop_index(
            _NEW_INDEX,
            table_name=_TABLE_NAME,
        )
    if _has_table() and not _has_index(_OLD_INDEX):
        op.create_index(
            _OLD_INDEX,
            "syllabus_alignment_runs",
            ["slm_document_id"],
            unique=True,
            postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
            sqlite_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
        )
