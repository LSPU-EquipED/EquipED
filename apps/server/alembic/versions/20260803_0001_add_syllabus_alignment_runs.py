"""add standalone syllabus alignment runs

Repair note (2026-08-08): this migration was never applied through the
stamped chain (the shared dev DB already carries the table and indexes via
out-of-band application), so upgrade/downgrade are conditional: they create
or drop the table and each index only when the target state differs. The
legacy-artifact backfill runs only when this migration creates the table,
so it can never insert duplicates on databases that already hold data.

Revision ID: 20260803_0001
Revises: 20260801_0001
Create Date: 2026-08-03
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "20260803_0001"
down_revision = "20260801_0001"
branch_labels = None
depends_on = None

_VALID_COMPLETED_LEVELS = {"MEETS", "PARTIALLY_MEETS", "DOES_NOT_MEET"}

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


def _backfill_legacy_alignment_artifacts() -> None:
    bind = op.get_bind()
    agent_results = sa.table(
        "agent_results",
        sa.column("document_id", sa.Uuid()),
        sa.column("evaluation_id", sa.Uuid()),
        sa.column("advisory_outputs", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    evaluation_jobs = sa.table(
        "evaluation_jobs",
        sa.column("evaluation_id", sa.Uuid()),
        sa.column("submitted_by", sa.Uuid()),
        sa.column("completed_at", sa.DateTime(timezone=True)),
    )
    documents = sa.table("documents", sa.column("document_id", sa.Uuid()))
    target = sa.table(
        "syllabus_alignment_runs",
        sa.column("alignment_id", sa.Uuid()),
        sa.column("slm_document_id", sa.Uuid()),
        sa.column("syllabus_document_id", sa.Uuid()),
        sa.column("requested_by", sa.Uuid()),
        sa.column("status", sa.String()),
        sa.column("alignment_level", sa.String()),
        sa.column("justification", sa.Text()),
        sa.column("alignment_artifact", sa.JSON()),
        sa.column("model_name", sa.String()),
        sa.column("provenance", sa.JSON()),
        sa.column("error_message", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("started_at", sa.DateTime(timezone=True)),
        sa.column("completed_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    rows = bind.execute(
        sa.select(
            agent_results.c.document_id,
            agent_results.c.advisory_outputs,
            agent_results.c.created_at,
            evaluation_jobs.c.submitted_by,
            evaluation_jobs.c.completed_at,
        ).select_from(
            agent_results.join(
                evaluation_jobs,
                agent_results.c.evaluation_id == evaluation_jobs.c.evaluation_id,
            )
        )
    ).mappings()
    known_documents = set(bind.execute(sa.select(documents.c.document_id)).scalars())
    for row in rows:
        advisory = row["advisory_outputs"] or {}
        artifact = (
            advisory.get("syllabus_alignment") if isinstance(advisory, dict) else None
        )
        if not isinstance(artifact, dict) or row["submitted_by"] is None:
            continue
        try:
            syllabus_id = uuid.UUID(str(artifact.get("syllabus_document_id")))
        except (TypeError, ValueError, AttributeError):
            continue
        if (
            row["document_id"] not in known_documents
            or syllabus_id not in known_documents
        ):
            continue
        level = str(artifact.get("status", "UNAVAILABLE"))
        processing_state = str(artifact.get("processing_state", "FAILED"))
        completed = processing_state == "COMPLETED" and level in _VALID_COMPLETED_LEVELS
        created_at = row["created_at"]
        completed_at = row["completed_at"] or created_at
        bind.execute(
            target.insert().values(
                alignment_id=uuid.uuid4(),
                slm_document_id=row["document_id"],
                syllabus_document_id=syllabus_id,
                requested_by=row["submitted_by"],
                status="COMPLETED" if completed else "FAILED",
                alignment_level=level if completed else "UNAVAILABLE",
                justification=str(
                    artifact.get("statement")
                    or "Legacy alignment result is unavailable."
                ),
                alignment_artifact=artifact,
                model_name=None,
                provenance={
                    "legacy_source": "agent_results.advisory_outputs",
                    "model_attribution": "unavailable",
                },
                error_message=None
                if completed
                else "Legacy alignment was incomplete or unavailable during migration.",
                created_at=created_at,
                started_at=created_at,
                completed_at=completed_at,
                updated_at=completed_at,
            )
        )


def upgrade() -> None:
    if not _has_table(_TABLE_NAME):
        _create_table()
        _create_indexes()
        if not op.get_context().as_sql:
            _backfill_legacy_alignment_artifacts()
    else:
        _create_indexes()


def downgrade() -> None:
    for index_name in _INDEX_NAMES:
        if _has_index(index_name):
            op.drop_index(index_name, table_name=_TABLE_NAME)
    if _has_table(_TABLE_NAME):
        op.drop_table(_TABLE_NAME)
