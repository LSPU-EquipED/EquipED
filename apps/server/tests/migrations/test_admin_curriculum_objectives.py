"""Offline migration checks: preserve identities and reject ambiguous legacy data."""

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext


@pytest.fixture
def legacy_db():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("user_id", sa.Uuid(), primary_key=True))
    courses = sa.Table(
        "courses", metadata, sa.Column("course_id", sa.Uuid(), primary_key=True)
    )
    objectives = sa.Table(
        "curriculum_objectives",
        metadata,
        sa.Column("objective_id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("program", sa.String(50), nullable=False),
        sa.UniqueConstraint("code", "program"),
    )
    cells = sa.Table(
        "curriculum_map_cells",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("courses.course_id")),
        sa.Column(
            "objective_id",
            sa.Uuid(),
            sa.ForeignKey("curriculum_objectives.objective_id"),
        ),
        sa.Column("level", sa.String(1)),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        ids = [uuid.uuid4() for _ in range(3)]
        connection.execute(courses.insert().values(course_id=ids[0]))
        connection.execute(
            objectives.insert().values(
                objective_id=ids[1],
                code="IT01",
                description="Original",
                program="BSInfoTech",
            )
        )
        connection.execute(
            cells.insert().values(
                id=ids[2], course_id=ids[0], objective_id=ids[1], level="E"
            )
        )
        path = (
            Path(__file__).resolve().parents[2]
            / "alembic/versions/20261023_0001_admin_curriculum_objectives.py"
        )
        spec = importlib.util.spec_from_file_location(
            "curriculum_admin_migration", path
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.op = Operations(MigrationContext.configure(connection))
        yield connection, migration, objectives, ids
    engine.dispose()


def test_upgrade_downgrade_preserve_objectives_and_mappings(legacy_db):
    connection, migration, _, ids = legacy_db
    migration.upgrade()
    row = (
        connection.execute(sa.text("SELECT * FROM curriculum_objectives"))
        .mappings()
        .one()
    )
    assert row["objective_id"] == ids[1].hex
    assert row["description"] == "Original"
    assert row["version"] == 1
    assert row["seed_code"] == "IT01"
    assert connection.scalar(sa.text("SELECT mapping_version FROM courses")) == 1
    assert connection.scalar(sa.text("SELECT level FROM curriculum_map_cells")) == "E"
    assert "curriculum_changes" in sa.inspect(connection).get_table_names()
    migration.downgrade()
    assert "version" not in {
        column["name"]
        for column in sa.inspect(connection).get_columns("curriculum_objectives")
    }
    assert (
        connection.scalar(sa.text("SELECT objective_id FROM curriculum_objectives"))
        == ids[1].hex
    )
    assert connection.scalar(sa.text("SELECT count(*) FROM curriculum_map_cells")) == 1


def test_migration_rejects_alias_duplicates_before_schema_changes(legacy_db):
    connection, migration, objectives, _ = legacy_db
    connection.execute(
        objectives.insert().values(
            objective_id=uuid.uuid4(),
            code=" it01 ",
            description="Other",
            program="BSIT",
        )
    )
    with pytest.raises(RuntimeError, match="duplicate"):
        migration.upgrade()
    assert "version" not in {
        column["name"]
        for column in sa.inspect(connection).get_columns("curriculum_objectives")
    }
