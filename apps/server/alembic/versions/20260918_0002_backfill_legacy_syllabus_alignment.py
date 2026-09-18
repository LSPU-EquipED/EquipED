"""backfill legacy syllabus alignment artifacts

Safe, additive data-only migration to backfill legacy syllabus alignment runs
from agent_results.advisory_outputs to syllabus_alignment_runs.

Runs after agent_results.advisory_outputs (20260808_0000) and syllabus_alignment_runs
(20260803_0001, 20260803_0002) are fully established.

Revision ID: 20260918_0002
Revises: 20260918_0001
Create Date: 2026-09-18
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "20260918_0002"
down_revision: str | None = "20260918_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALID_COMPLETED_LEVELS = {"MEETS", "PARTIALLY_MEETS", "DOES_NOT_MEET"}


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    if op.get_context().as_sql:
        return

    if not _has_table("syllabus_alignment_runs"):
        return
    if not _has_table("agent_results") or not _has_column(
        "agent_results", "advisory_outputs"
    ):
        return
    if not _has_table("evaluation_jobs") or not _has_table("documents"):
        return

    bind = op.get_bind()
    agent_results = sa.table(
        "agent_results",
        sa.column("agent_result_id", sa.Uuid()),
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

    existing_slms = set(bind.execute(sa.select(target.c.slm_document_id)).scalars())

    rows = (
        bind.execute(
            sa.select(
                agent_results.c.agent_result_id,
                agent_results.c.document_id,
                agent_results.c.advisory_outputs,
                agent_results.c.created_at,
                evaluation_jobs.c.submitted_by,
                evaluation_jobs.c.completed_at,
            )
            .select_from(
                agent_results.join(
                    evaluation_jobs,
                    agent_results.c.evaluation_id == evaluation_jobs.c.evaluation_id,
                )
            )
            .order_by(
                agent_results.c.created_at.desc(),
                agent_results.c.agent_result_id.desc(),
            )
        )
        .mappings()
        .all()
    )

    known_documents = set(bind.execute(sa.select(documents.c.document_id)).scalars())

    for row in rows:
        slm_id = row["document_id"]
        if slm_id in existing_slms:
            continue

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
        if slm_id not in known_documents or syllabus_id not in known_documents:
            continue
        level = str(artifact.get("status", "UNAVAILABLE"))
        processing_state = str(artifact.get("processing_state", "FAILED"))
        completed = processing_state == "COMPLETED" and level in _VALID_COMPLETED_LEVELS
        created_at = row["created_at"]
        completed_at = row["completed_at"] or created_at
        bind.execute(
            target.insert().values(
                alignment_id=uuid.uuid4(),
                slm_document_id=slm_id,
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
        existing_slms.add(slm_id)


def downgrade() -> None:
    # Additive migration: data backfilled from legacy advisory_outputs is preserved.
    pass
