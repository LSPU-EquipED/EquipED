"""Preserve rubric identity for immutable evaluation form snapshots.

Revision ID: 20261011_0001
Revises: 20261010_0002
Create Date: 2026-10-11 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261011_0001"
down_revision: str | None = "20261010_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SNAPSHOT_RUBRIC_FK = "fk_eval_snapshots_rubric_set_id"
_PROVENANCE_SNAPSHOT_FK = "fk_eval_snapshots_rubric_provenance_id"


def _replace_snapshot_rubric_fk(*, to_provenance: bool) -> None:
    """Replace the snapshot rubric FK using the dialect-safe convention."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "evaluation_form_snapshots", recreate="always"
        ) as batch_op:
            batch_op.drop_constraint(
                _SNAPSHOT_RUBRIC_FK if to_provenance else _PROVENANCE_SNAPSHOT_FK,
                type_="foreignkey",
            )
            batch_op.create_foreign_key(
                _PROVENANCE_SNAPSHOT_FK if to_provenance else _SNAPSHOT_RUBRIC_FK,
                "evaluation_rubric_provenance" if to_provenance else "rubric_sets",
                ["rubric_set_id"],
                ["rubric_set_id"],
            )
        return

    op.drop_constraint(
        _SNAPSHOT_RUBRIC_FK if to_provenance else _PROVENANCE_SNAPSHOT_FK,
        "evaluation_form_snapshots",
        type_="foreignkey",
    )
    op.create_foreign_key(
        _PROVENANCE_SNAPSHOT_FK if to_provenance else _SNAPSHOT_RUBRIC_FK,
        "evaluation_form_snapshots",
        "evaluation_rubric_provenance" if to_provenance else "rubric_sets",
        ["rubric_set_id"],
        ["rubric_set_id"],
    )


def upgrade() -> None:
    op.create_table(
        "evaluation_rubric_provenance",
        sa.Column("rubric_set_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("agent_id", sa.String(length=50), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("adapter_key", sa.String(length=50), nullable=False),
        sa.Column("adapter_version", sa.Integer(), nullable=False),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Keep only identity metadata. Criteria and payloads remain in their
    # respective authoring/snapshot tables; this backfill covers every agent.
    op.execute(
        sa.text(
            "INSERT INTO evaluation_rubric_provenance "
            "(rubric_set_id, agent_id, version_number, name, adapter_key, "
            "adapter_version, archived_at) "
            "SELECT DISTINCT rs.rubric_set_id, rs.agent_id, rs.version_number, "
            "rs.name, rs.adapter_key, rs.adapter_version, "
            "COALESCE(rs.retired_at, CURRENT_TIMESTAMP) "
            "FROM evaluation_form_snapshots efs "
            "JOIN rubric_sets rs ON rs.rubric_set_id = efs.rubric_set_id"
        )
    )
    _replace_snapshot_rubric_fk(to_provenance=True)


def downgrade() -> None:
    bind = op.get_bind()
    missing_snapshot_sets = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM evaluation_form_snapshots efs "
            "LEFT JOIN rubric_sets rs ON rs.rubric_set_id = efs.rubric_set_id "
            "WHERE rs.rubric_set_id IS NULL"
        )
    ).scalar_one()
    orphan_provenance = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM evaluation_rubric_provenance p "
            "LEFT JOIN rubric_sets rs ON rs.rubric_set_id = p.rubric_set_id "
            "WHERE rs.rubric_set_id IS NULL"
        )
    ).scalar_one()
    if missing_snapshot_sets or orphan_provenance:
        raise RuntimeError(
            "Cannot downgrade rubric provenance: restore every referenced and "
            "provenance rubric_set row before removing historical provenance"
        )

    _replace_snapshot_rubric_fk(to_provenance=False)
    op.drop_table("evaluation_rubric_provenance")
