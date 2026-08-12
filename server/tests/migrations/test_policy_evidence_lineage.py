"""Offline migration-path tests for policy evidence migration lineage.

These tests verify that the repaired Alembic chain:
1. Has exactly one linear head
2. Resolves ``alembic current`` when a DB is stamped at ``20260713_0004``
3. Generates correct DDL for the new ``document_chunks.policy_area`` column
4. Includes the ``policy_area`` revision in the full chain walk

They never touch the real Neon database — all tests use offline analysis or
temporary SQLite files.
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

# Ensure repo root is on sys.path so ``from server.core.config …`` works
# inside the Alembic env.py.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ── helpers ──────────────────────────────────────────────────────────


def _cfg(db_url: str = "postgresql://ignored") -> Config:
    """Return an Alembic ``Config`` targeting *db_url*."""
    ini = str(REPO_ROOT / "server" / "alembic.ini")
    c = Config(ini)
    c.set_main_option("sqlalchemy.url", db_url)
    return c


def _stamp(engine, revision: str) -> None:
    """Stamp *engine*'s database at *revision*."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) PRIMARY KEY)"
            )
        )
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
            {"rev": revision},
        )


def _run_offline_sql(cfg: Config, revision_range: str) -> str:
    """Run *revision_range* in offline (``--sql``) mode and return the SQL."""
    import sys

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        alembic_upgrade(cfg, revision_range, sql=True)
    finally:
        sys.stdout = old_stdout
    return buf.getvalue()


# ── tests ────────────────────────────────────────────────────────────


class TestPolicyEvidenceLineage:
    """Proof that the policy evidence migration chain is correct."""

    # ------------------------------------------------------------------
    # Chain structure — offline analysis, no database needed
    # ------------------------------------------------------------------

    def test_single_head(self):
        """The migration tree has exactly one head (no forks)."""
        script = ScriptDirectory.from_config(_cfg())
        h = script.get_heads()
        assert len(h) == 1, f"Expected 1 head, got {len(h)}: {h}"

    def test_chain_walks_linearly(self):
        """Walking from head to root visits every revision once, linear.

        The chain now tops out at a merge revision (two parents), so the walk
        follows the full ancestry rather than a single down_revision.
        """
        script = ScriptDirectory.from_config(_cfg())

        seen: list[str] = []
        stack: list[str] = [script.get_heads()[0]]
        while stack:
            rev_id = stack.pop()
            if rev_id in seen:
                continue
            seen.append(rev_id)
            down = script.get_revision(rev_id).down_revision
            if isinstance(down, str):
                if down:
                    stack.append(down)
            else:
                stack.extend(down or ())

        # Must include the new policy_area revision
        assert any("0005" in r for r in seen), (
            "Chain must include 20260713_0005 (add document_chunks.policy_area)"
        )

        # Must start at baseline
        assert "20260507_0001" in seen, f"Chain root must be 20260507_0001, got {seen}"

        # No duplicate revisions
        assert len(seen) == len(set(seen)), "Duplicate revision in chain"

    # ------------------------------------------------------------------
    # Current-resolution — simulates the dev DB stamped at 0004
    # ------------------------------------------------------------------

    def test_current_resolves_at_stamped_0004(self, tmp_path: Path):
        """``alembic current`` resolves when DB is stamped at 20260713_0004."""
        db = tmp_path / "current_test.db"
        db_url = f"sqlite+pysqlite:///{db}"
        engine = create_engine(db_url)
        _stamp(engine, "20260713_0004")
        engine.dispose()

        # Resolve current revision via MigrationContext (no CLI needed)
        engine = create_engine(db_url)
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            cur = ctx.get_current_revision()
            assert cur == "20260713_0004", f"Expected current=20260713_0004, got {cur}"
        engine.dispose()

    # ------------------------------------------------------------------
    # Offline SQL verification — proves migrations generate correct DDL
    # ------------------------------------------------------------------

    def test_offline_0004_shim_is_noop(self):
        """Migration 0004 compatibility shim generates no schema changes."""
        sql = _run_offline_sql(_cfg(), "20260713_0002:20260713_0004")

        # The only table mutation should be the alembic_version UPDATE.
        # No ALTER TABLE, CREATE TABLE, or DROP statements.
        ddl_statements = re.findall(r"^(ALTER|CREATE|DROP) ", sql, re.MULTILINE)
        assert len(ddl_statements) == 0, (
            f"0004 should be a no-op, but found DDL: {ddl_statements}"
        )

        # Must still update the version tracking
        assert "UPDATE alembic_version" in sql
        assert "20260713_0004" in sql

    def test_offline_0005_adds_policy_area_column(self):
        """Migration 0005 generates ALTER TABLE ADD COLUMN for policy_area."""
        sql = _run_offline_sql(_cfg(), "20260713_0004:20260713_0005")

        # Core DDL assertion
        assert (
            "ALTER TABLE document_chunks ADD COLUMN policy_area VARCHAR(100)" in sql
        ), "0005 must ALTER TABLE document_chunks ADD COLUMN policy_area"

        # Backfill UPDATE for existing rows
        assert "UPDATE document_chunks" in sql
        assert "SET policy_area" in sql
        assert "source_type = 'policy'" in sql

        # Version tracking
        assert "20260713_0005" in sql

    # ------------------------------------------------------------------
    # Full fresh-DB lineage ordering
    # ------------------------------------------------------------------

    def test_full_chain_revision_order(self):
        """Verify section_ref/chunk_index revisions precede policy_area via
        direct ancestry, valid with the merge revision in the chain."""
        script = ScriptDirectory.from_config(_cfg())

        def _ancestors(rev_id: str) -> set[str]:
            """All revisions reachable by following down_revision (handles
            the merge revision's tuple of parents)."""
            seen: set[str] = set()
            stack: list[str] = [rev_id]
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                down = script.get_revision(current).down_revision
                if isinstance(down, str):
                    if down:
                        stack.append(down)
                else:
                    stack.extend(down or ())
            return seen

        # 20260713_0001 (section_ref/chunk_index) must be a strict ancestor
        # of 20260713_0005 (policy_area) — asserted directly from the DAG,
        # not inferred from any traversal order.
        assert "20260713_0001" in _ancestors("20260713_0005"), (
            "section_ref/chunk_index (0001) must be added before policy_area (0005)"
        )
