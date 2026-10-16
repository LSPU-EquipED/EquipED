"""Reconstruct the program outcomes and citation cache tables.

Revision ID: 20261015_0001
Revises: 20261011_0001
Create Date: 2026-10-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_0001"
down_revision: str | None = "20261011_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CITATION_CACHE_ID_SEQUENCE = "citation_cache_id_seq"


def _citation_cache_id_column() -> sa.Column:
    """Use the observed PostgreSQL sequence and SQLite's native rowid."""
    if op.get_bind().dialect.name == "postgresql":
        sequence = sa.Sequence(
            _CITATION_CACHE_ID_SEQUENCE,
            schema="public",
            start=1,
            increment=1,
        )
        op.execute(sa.schema.CreateSequence(sequence))
        return sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            nullable=False,
            server_default=sequence.next_value(),
        )

    return sa.Column(
        "id",
        sa.Integer(),
        primary_key=True,
        nullable=False,
        autoincrement=True,
    )


def upgrade() -> None:
    op.create_table(
        "program_outcomes",
        sa.Column("program_outcome_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("program_code", sa.String(length=50), nullable=True),
        sa.Column("program_name", sa.String(length=200), nullable=False),
        sa.Column("outcome_id", sa.String(length=20), nullable=False),
        sa.Column("program_outcome", sa.Text(), nullable=False),
        sa.Column("performance_indicator", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_program_outcomes_program_code",
        "program_outcomes",
        ["program_code"],
    )

    op.create_table(
        "citation_cache",
        _citation_cache_id_column(),
        sa.Column("doi_hash", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column(
            "cached_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retain_until", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("doi_hash", name="uq_citation_cache_doi_hash"),
    )
    op.create_index("ix_citation_cache_doi_hash", "citation_cache", ["doi_hash"])
    op.create_index("ix_citation_cache_expires_at", "citation_cache", ["expires_at"])
    op.create_index(
        "ix_citation_cache_retain_until",
        "citation_cache",
        ["retain_until"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER SEQUENCE public.citation_cache_id_seq "
                "OWNED BY public.citation_cache.id"
            )
        )


def downgrade() -> None:
    op.drop_index("ix_citation_cache_retain_until", table_name="citation_cache")
    op.drop_index("ix_citation_cache_expires_at", table_name="citation_cache")
    op.drop_index("ix_citation_cache_doi_hash", table_name="citation_cache")
    op.drop_table("citation_cache")

    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("DROP SEQUENCE IF EXISTS public.citation_cache_id_seq"))

    op.drop_index("ix_program_outcomes_program_code", table_name="program_outcomes")
    op.drop_table("program_outcomes")
