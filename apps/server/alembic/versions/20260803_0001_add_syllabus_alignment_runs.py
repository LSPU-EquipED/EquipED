"""add standalone syllabus alignment runs

Repair note: this migration was conditionally written because the development
database already carried the table and indexes via out-of-band application.
Upgrade and downgrade are conditional: they create or drop the table and
indexes only when the target state differs.

Legacy alignment artifact backfill is handled exclusively by revision
`20260918_0002_backfill_legacy_syllabus_alignment`, after both
`agent_results.advisory_outputs` (20260808_0000) and `syllabus_alignment_runs`
(20260803_0001, 20260803_0002) are fully established in the migration lineage.

Revision ID: 20260803_0001
Revises: 20260801_0001
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260803_0001"
down_revision = "20260801_0001"
branch_labels = None
depends_on = None

_TABLE_NAME = "syllabus_alignment_runs"
_INDEX_NAMES = (
    "idx_syllabus_alignment_owner_created",
    "idx_syllabus_alignment_slm_created",
    "idx_syllabus_alignment_syllabus",
    "uq_syllabus_alignment_active_slm",
)


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def _has_index(name: str) -> bool:
    bind = op.get_bind()
    return name in [i["name"] for i in inspect(bind).get_indexes(_TABLE_NAME)]


def _create_table() -> None:
    op.create_table(
        "syllabus_alignment_runs",
        sa.Column("alignment_id", sa.Uuid(), nullable=False),
        sa.Column("slm_document_id", sa.Uuid(), nullable=False),
        sa.Column("syllabus_document_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("alignment_level", sa.String(length=30), nullable=True),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("alignment_artifact", sa.JSON(), nullable=True),
        sa.Column("model_name", sa.String(length=200), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_syllabus_alignment_status",
        ),
        sa.CheckConstraint(
            "(status IN ('QUEUED', 'RUNNING') AND alignment_level IS NULL) OR "
            "(status = 'COMPLETED' AND alignment_level IN "
            "('MEETS', 'PARTIALLY_MEETS', 'DOES_NOT_MEET')) OR "
            "(status = 'FAILED' AND alignment_level = 'UNAVAILABLE')",
            name="ck_syllabus_alignment_level_for_status",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["slm_document_id"], ["documents.document_id"]),
        sa.ForeignKeyConstraint(["syllabus_document_id"], ["documents.document_id"]),
        sa.PrimaryKeyConstraint("alignment_id"),
    )


def _create_indexes() -> None:
    if not _has_index("idx_syllabus_alignment_owner_created"):
        op.create_index(
            "idx_syllabus_alignment_owner_created",
            "syllabus_alignment_runs",
            ["requested_by", "created_at"],
        )
    if not _has_index("idx_syllabus_alignment_slm_created"):
        op.create_index(
            "idx_syllabus_alignment_slm_created",
            "syllabus_alignment_runs",
            ["slm_document_id", "created_at"],
        )
    if not _has_index("idx_syllabus_alignment_syllabus"):
        op.create_index(
            "idx_syllabus_alignment_syllabus",
            "syllabus_alignment_runs",
            ["syllabus_document_id"],
        )
    if not _has_index("uq_syllabus_alignment_active_slm"):
        op.create_index(
            "uq_syllabus_alignment_active_slm",
            "syllabus_alignment_runs",
            ["slm_document_id"],
            unique=True,
            postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
            sqlite_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
        )


def upgrade() -> None:
    if not _has_table(_TABLE_NAME):
        _create_table()
        _create_indexes()
    else:
        _create_indexes()


def downgrade() -> None:
    for index_name in _INDEX_NAMES:
        if _has_index(index_name):
            op.drop_index(index_name, table_name=_TABLE_NAME)
    if _has_table(_TABLE_NAME):
        op.drop_table(_TABLE_NAME)
