"""retain one current syllabus alignment result per SLM

Revision ID: 20260803_0002
Revises: 20260803_0001
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260803_0002"
down_revision = "20260803_0001"
branch_labels = None
depends_on = None


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

    op.drop_index(
        "uq_syllabus_alignment_active_slm",
        table_name="syllabus_alignment_runs",
    )
    op.create_index(
        "uq_syllabus_alignment_slm",
        "syllabus_alignment_runs",
        ["slm_document_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_syllabus_alignment_slm",
        table_name="syllabus_alignment_runs",
    )
    op.create_index(
        "uq_syllabus_alignment_active_slm",
        "syllabus_alignment_runs",
        ["slm_document_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
        sqlite_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )
