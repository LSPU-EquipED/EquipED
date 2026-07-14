"""Create final model_validation and criterion_score tables

Supports two upgrade paths:
- Fresh DB: create both tables with full schema, indexes, and constraints.
- Legacy DB (tables already exist from fragmented 0001+0002+0003): inspect
  existing shape; skip create; add only missing nullable columns, indexes, or
  constraints when safely absent; fail with a clear migration error for
  incompatible non-additive shapes (e.g. an undropped expected_score column
  on model_validations, or missing required non-nullable columns).

All production application code remains free of schema reflection or
conditional table behavior — this is migration-time only.

Revision ID: 20260714_0001
Revises: 20260713_0005
Create Date: 2026-07-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_0001"
down_revision: str | Sequence[str] | None = "20260713_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Canonical column definitions — single source of truth for both paths.
# ---------------------------------------------------------------------------

_MODEL_VALIDATIONS_COLUMNS: list[sa.Column] = [
    sa.Column("validation_id", sa.Uuid(), nullable=False),
    sa.Column("evaluation_id", sa.Uuid(), nullable=False),
    sa.Column("toxicity_score", sa.Numeric(5, 4), nullable=True),
    sa.Column("toxicity_label", sa.String(length=30), nullable=True),
    sa.Column("toxicity_explanation", sa.Text(), nullable=True),
    sa.Column("toxicity_model", sa.String(length=200), nullable=True),
    sa.Column("toxicity_error", sa.Text(), nullable=True),
    sa.Column("toxicity_assessed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),
]

_MODEL_VALIDATIONS_REQUIRED = {
    "validation_id",
    "evaluation_id",
    "created_by",
    "created_at",
}

_MODEL_VALIDATIONS_FORBIDDEN = {"expected_score"}

_CRITERION_COLUMNS: list[sa.Column] = [
    sa.Column("expected_score_id", sa.Uuid(), nullable=False),
    sa.Column("validation_id", sa.Uuid(), nullable=False),
    sa.Column("agent_id", sa.String(length=50), nullable=False),
    sa.Column("criterion_id", sa.String(length=100), nullable=False),
    sa.Column("criterion_title", sa.String(length=300), nullable=False),
    sa.Column("expected_score", sa.Integer(), nullable=False),
    sa.Column("actual_score", sa.Integer(), nullable=True),
    sa.Column("absolute_error", sa.Numeric(3, 2), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),
]

_CRITERION_REQUIRED = {
    "expected_score_id",
    "validation_id",
    "agent_id",
    "criterion_id",
    "criterion_title",
    "expected_score",
    "created_at",
    "updated_at",
}


def _existing_table(name: str) -> bool:
    """Return True if the table already exists in the database.

    In offline (``--sql``) mode the bind is either unavailable or is a
    MockConnection; we conservatively return False and let the fresh
    DDL-generating path run (the generated SQL will do the right thing).
    """
    try:
        from sqlalchemy import inspect
        from sqlalchemy.engine.mock import MockConnection

        bind = op.get_bind()
        if isinstance(bind, MockConnection):
            return False  # offline mode — assume fresh
    except Exception:
        return False  # offline mode — assume fresh
    inspector = inspect(bind)
    return name in inspector.get_table_names()


def _existing_columns(name: str) -> set[str]:
    """Return the set of column names currently on the table."""
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    return {c["name"] for c in inspector.get_columns(name)}


def _existing_indexes(name: str) -> set[str]:
    """Return the set of index names currently on the table."""
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    return {ix["name"] for ix in inspector.get_indexes(name) if ix["name"]}


def _add_missing_columns(
    table: str,
    all_columns: list[sa.Column],
    existing: set[str],
    required: set[str],
    forbidden: set[str] | None = None,
) -> None:
    """Add columns present in *all_columns* but missing from *existing*.

    Forbidden columns that *are* found in *existing* raise an informative
    error — the operator must fix the schema manually.
    Required columns missing from *existing* also raise.
    """
    if forbidden is not None:
        found_forbidden = existing & forbidden
        if found_forbidden:
            raise Exception(
                f"Migration {revision}: table '{table}' contains incompatible "
                f"column(s) {sorted(found_forbidden)} that should have been "
                f"removed by a prior migration. "
                f"Manually drop {sorted(found_forbidden)} from '{table}' "
                f"and re-run this migration, or run the full legacy "
                f"0001→0002→0003 chain first."
            )

    missing_required = required - existing
    if missing_required:
        raise Exception(
            f"Migration {revision}: table '{table}' is missing required "
            f"column(s) {sorted(missing_required)}. "
            f"These cannot be added as nullable-only additive changes. "
            f"Ensure the legacy 0001→0002→0003 migration chain has run, "
            f"or run on a fresh database."
        )

    for col in all_columns:
        name = col.name
        if name not in existing:
            if not col.nullable:
                raise Exception(
                    f"Migration {revision}: cannot add non-nullable column "
                    f"'{name}' to existing table '{table}' — it would "
                    f"require a default or backfill. "
                    f"Run the legacy migration chain instead."
                )
            op.add_column(table, col)


def _add_missing_index(
    index_name: str, table: str, columns: list[str], existing: set[str]
) -> None:
    """Create an index if it does not already exist."""
    if index_name not in existing:
        op.create_index(index_name, table, columns)


def _add_missing_unique_constraint(
    constraint_name: str, table: str, columns: list[str], existing_ix: set[str]
) -> None:
    """Add a UNIQUE constraint via create_index(unique=True).

    SQLite does not support ALTER TABLE ADD CONSTRAINT for UNIQUE, so we
    use create_index with unique=True instead. Works on both SQLite and
    Postgres. Skip if an index with this name already exists (SQLite
    implements unique constraints as unique indexes internally).
    """
    if constraint_name not in existing_ix:
        op.create_index(constraint_name, table, columns, unique=True)


def upgrade() -> None:
    if _existing_table("model_validations"):
        _upgrade_legacy()
    else:
        _upgrade_fresh()


def _upgrade_fresh() -> None:
    """Create both tables from scratch."""
    _create_model_validations_table()
    _create_criterion_scores_table()


def _create_model_validations_table() -> None:
    op.create_table(
        "model_validations",
        sa.Column("validation_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("toxicity_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("toxicity_label", sa.String(length=30), nullable=True),
        sa.Column("toxicity_explanation", sa.Text(), nullable=True),
        sa.Column("toxicity_model", sa.String(length=200), nullable=True),
        sa.Column("toxicity_error", sa.Text(), nullable=True),
        sa.Column("toxicity_assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["evaluation_jobs.evaluation_id"]
        ),
        sa.PrimaryKeyConstraint("validation_id"),
    )
    op.create_index(
        "uq_model_validations_evaluation",
        "model_validations",
        ["evaluation_id"],
        unique=True,
    )
    op.create_index(
        "idx_model_validations_created_by",
        "model_validations",
        ["created_by"],
    )


def _create_criterion_scores_table() -> None:
    op.create_table(
        "model_validation_criterion_scores",
        sa.Column("expected_score_id", sa.Uuid(), nullable=False),
        sa.Column("validation_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.String(length=50), nullable=False),
        sa.Column("criterion_id", sa.String(length=100), nullable=False),
        sa.Column("criterion_title", sa.String(length=300), nullable=False),
        sa.Column("expected_score", sa.Integer(), nullable=False),
        sa.Column("actual_score", sa.Integer(), nullable=True),
        sa.Column("absolute_error", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["validation_id"], ["model_validations.validation_id"]
        ),
        sa.PrimaryKeyConstraint("expected_score_id"),
    )
    op.create_index(
        "uq_validation_agent_criterion",
        "model_validation_criterion_scores",
        ["validation_id", "agent_id", "criterion_id"],
        unique=True,
    )
    op.create_index(
        "idx_validation_criterion_validation",
        "model_validation_criterion_scores",
        ["validation_id"],
    )


def _upgrade_legacy() -> None:
    """Inspect existing tables, add missing additive items, fail on
    incompatible shapes."""

    # ---- model_validations ----
    mv_cols = _existing_columns("model_validations")
    mv_ix = _existing_indexes("model_validations")

    _add_missing_columns(
        "model_validations",
        _MODEL_VALIDATIONS_COLUMNS,
        mv_cols,
        _MODEL_VALIDATIONS_REQUIRED,
        forbidden=_MODEL_VALIDATIONS_FORBIDDEN,
    )

    # model_validations FKs and PK are already present from legacy 0001.
    # Add missing unique constraint and index.
    _add_missing_unique_constraint(
        "uq_model_validations_evaluation",
        "model_validations",
        ["evaluation_id"],
        mv_ix,
    )
    _add_missing_index(
        "idx_model_validations_created_by",
        "model_validations",
        ["created_by"],
        mv_ix,
    )

    # ---- model_validation_criterion_scores ----
    crit_table = "model_validation_criterion_scores"
    if not _existing_table(crit_table):
        _create_criterion_scores_table()
        return

    crit_cols = _existing_columns(crit_table)
    crit_ix = _existing_indexes(crit_table)

    _add_missing_columns(
        crit_table,
        _CRITERION_COLUMNS,
        crit_cols,
        _CRITERION_REQUIRED,
    )

    _add_missing_unique_constraint(
        "uq_validation_agent_criterion",
        crit_table,
        ["validation_id", "agent_id", "criterion_id"],
        crit_ix,
    )
    _add_missing_index(
        "idx_validation_criterion_validation",
        crit_table,
        ["validation_id"],
        crit_ix,
    )

    # Create a marker so downgrade knows these tables pre-existed
    # and should not be dropped.
    _create_legacy_marker()


def _create_legacy_marker() -> None:
    """Create a small sentinel table indicating the legacy upgrade path
    was taken (tables pre-existed). The downgrade checks for this marker
    to decide whether to drop the application tables."""
    op.create_table(
        "_m20260714_0001_legacy",
        sa.Column("dummy", sa.Integer(), nullable=False),
    )


def _is_legacy_upgrade() -> bool:
    """Return True if the upgrade ran on a legacy DB (tables pre-existed).

    Checks for the sentinel marker table created by _create_legacy_marker.
    """
    return _existing_table("_m20260714_0001_legacy")


def _drop_legacy_marker() -> None:
    """Drop the legacy marker table."""
    try:
        op.drop_table("_m20260714_0001_legacy")
    except Exception:
        pass


def _is_offline() -> bool:
    """Return True if running in offline (``--sql``) mode."""
    try:
        from sqlalchemy.engine.mock import MockConnection

        bind = op.get_bind()
        return isinstance(bind, MockConnection)
    except Exception:
        return False


def downgrade() -> None:
    """Drop tables created by this migration.

    Fresh-path downgrade: drop both application tables unconditionally.
    Legacy-path downgrade: tables pre-existed, so only drop the legacy
    marker table — the actual tables survive for the legacy chain
    (0001→0002→0003) to handle.

    In offline (``--sql``) mode we cannot determine which path was taken,
    so we always emit the fresh-path DDL (DROP TABLE statements). If the
    tables do not exist at execution time the statements are harmless.
    """
    if not _is_offline() and _is_legacy_upgrade():
        # Tables pre-existed from old fragmented migrations. Drop only
        # the marker; the application tables survive so the legacy
        # chain can downgrade them in turn.
        _drop_legacy_marker()
        return

    if _is_offline():
        # Offline mode: emit DDL for the fresh path unconditionally.
        pass
    elif not _existing_table("model_validations"):
        return  # nothing to do

    # Fresh path — we created both tables; drop them cleanly.
    try:
        op.drop_index(
            "idx_validation_criterion_validation",
            table_name="model_validation_criterion_scores",
        )
    except Exception:
        pass
    try:
        op.drop_table("model_validation_criterion_scores")
    except Exception:
        pass
    try:
        op.drop_index(
            "idx_model_validations_created_by", table_name="model_validations"
        )
    except Exception:
        pass
    try:
        op.drop_table("model_validations")
    except Exception:
        pass
