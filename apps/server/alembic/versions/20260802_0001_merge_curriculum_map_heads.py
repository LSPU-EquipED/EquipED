"""Merge curriculum-map feature head with the program-confirmed head.

Both feature branches diverge from 20260716_0001:
- 20260730_0001 (curriculum-map tables, this branch)
- 20260801_0001 (evaluation_jobs.confirmed_program, main)

This no-op merge makes the chain linear again so ``alembic heads`` reports
exactly one head; the subsequent hardening revision
(20260802_0002) applies schema fixes on top.

Revision ID: 20260802_0001
Revises: 20260730_0001, 20260801_0001
Create Date: 2026-08-02
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260802_0001"
down_revision: tuple[str, ...] = ("20260730_0001", "20260801_0001")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge branch heads — no schema change."""


def downgrade() -> None:
    """Unmerge branch heads — no schema change."""
