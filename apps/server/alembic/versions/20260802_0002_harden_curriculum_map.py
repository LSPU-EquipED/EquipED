"""Harden curriculum-map schema and normalize the legacy BSIT program alias.

Applied after the 20260802_0001 merge. Does three things:

1. Normalizes existing ``courses``/``curriculum_objectives`` rows that carry
   the legacy ``BSIT`` program alias to the canonical ``BSInfoTech``.
   ``BSInfoTech`` is the only authoritative program for this feature until an
   authoritative BSCS map exists. Normalization refuses to run when a legacy
   ``BSIT`` objective would collide with an existing ``BSInfoTech`` objective
   of the same code (the ``(code, program)`` unique constraint would
   otherwise collapse two distinct institutional rows) — it fails loudly
   instead of merging silently. ``courses.course_code`` is globally unique,
   so course normalization cannot collide.
2. Adds a nullable JSON ``provenance`` column to
   ``curriculum_alignment_checks`` for per-check attribution metadata.
3. Adds indexes for ``curriculum_map_cells.course_id`` and for
   ``curriculum_alignment_checks`` ``(document_id, run_at)`` and
   ``course_id``.

The migration is fully reversible without persistent bookkeeping:
``downgrade()`` preflights the inverse collision (a ``BSInfoTech`` objective
whose code already exists as ``BSIT``) and then normalizes every
``BSInfoTech`` course/objective row back to the legacy ``BSIT`` alias, so a
subsequent legacy (``BSIT``) reseed cannot trip the ``(code, program)``
unique constraint.

Revision ID: 20260802_0002
Revises: 20260802_0001
Create Date: 2026-08-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260802_0002"
down_revision: str | None = "20260802_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CANONICAL_PROGRAM = "BSInfoTech"
LEGACY_PROGRAM = "BSIT"


def _is_offline() -> bool:
    """Return True when generating offline (``--sql``) DDL.

    Offline generation has no live connection, so data-dependent guards
    (the alias-collision checks) cannot run and are assumed to hold.
    """
    try:
        from sqlalchemy.engine.mock import MockConnection

        return isinstance(op.get_bind(), MockConnection)
    except Exception:
        return False


def _conflicting_objective_codes(from_program: str, to_program: str) -> list[str]:
    """Codes that would collide if rows moved from *from_program* to
    *to_program* (rows in the target program already carry the code)."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT code FROM curriculum_objectives"
            " WHERE program = :from_program AND code IN ("
            "   SELECT code FROM curriculum_objectives WHERE program = :to_program"
            " )"
        ).bindparams(from_program=from_program, to_program=to_program)
    ).fetchall()
    return sorted({row[0] for row in rows})


def _fail_on_collision(codes: list[str], direction: str) -> None:
    if not codes:
        return
    codes_str = ", ".join(codes)
    if direction == "up":
        raise RuntimeError(
            "Cannot normalize legacy BSIT curriculum objectives to "
            "BSInfoTech: BSInfoTech objectives with the same code already "
            f"exist for [{codes_str}]. Resolve the duplicate institutional "
            "objectives before upgrading."
        )
    raise RuntimeError(
        "Cannot downgrade BSInfoTech curriculum objectives to BSIT: BSIT "
        "objectives with the same code already exist for "
        f"[{codes_str}]. Resolve the duplicate institutional objectives "
        "before downgrading."
    )


def upgrade() -> None:
    # Refuse to normalize when a legacy BSIT objective shares its code with an
    # existing BSInfoTech objective — merging them would silently collapse two
    # potentially different institutional rows into one.
    if not _is_offline():
        _fail_on_collision(
            _conflicting_objective_codes(LEGACY_PROGRAM, CANONICAL_PROGRAM), "up"
        )

    # courses.course_code is globally unique (uq_courses_course_code), so a
    # plain program update cannot collide with an existing BSInfoTech row.
    op.execute(
        sa.text(
            "UPDATE curriculum_objectives SET program = :canonical"
            " WHERE program = :legacy"
        ).bindparams(canonical=CANONICAL_PROGRAM, legacy=LEGACY_PROGRAM)
    )
    op.execute(
        sa.text(
            "UPDATE courses SET program = :canonical WHERE program = :legacy"
        ).bindparams(canonical=CANONICAL_PROGRAM, legacy=LEGACY_PROGRAM)
    )

    op.add_column(
        "curriculum_alignment_checks",
        sa.Column("provenance", sa.JSON(), nullable=True),
    )
    op.create_index(
        "idx_curriculum_map_cells_course_id",
        "curriculum_map_cells",
        ["course_id"],
    )
    op.create_index(
        "idx_curriculum_alignment_checks_document_run_at",
        "curriculum_alignment_checks",
        ["document_id", "run_at"],
    )
    op.create_index(
        "idx_curriculum_alignment_checks_course_id",
        "curriculum_alignment_checks",
        ["course_id"],
    )


def downgrade() -> None:
    # Preflight before any schema change so a failed downgrade leaves nothing
    # half-applied (SQLite DDL is non-transactional in Alembic).
    if not _is_offline():
        _fail_on_collision(
            _conflicting_objective_codes(CANONICAL_PROGRAM, LEGACY_PROGRAM), "down"
        )

    op.drop_index(
        "idx_curriculum_alignment_checks_course_id",
        table_name="curriculum_alignment_checks",
    )
    op.drop_index(
        "idx_curriculum_alignment_checks_document_run_at",
        table_name="curriculum_alignment_checks",
    )
    op.drop_index(
        "idx_curriculum_map_cells_course_id",
        table_name="curriculum_map_cells",
    )
    op.drop_column("curriculum_alignment_checks", "provenance")

    # Normalize every canonical row back to the legacy alias so the database
    # exactly reproduces the pre-feature state and a legacy BSIT reseed cannot
    # create (code, program) duplicates.
    op.execute(
        sa.text(
            "UPDATE curriculum_objectives SET program = :legacy"
            " WHERE program = :canonical"
        ).bindparams(legacy=LEGACY_PROGRAM, canonical=CANONICAL_PROGRAM)
    )
    op.execute(
        sa.text(
            "UPDATE courses SET program = :legacy WHERE program = :canonical"
        ).bindparams(legacy=LEGACY_PROGRAM, canonical=CANONICAL_PROGRAM)
    )
