"""add curriculum map tables (courses, objectives, map cells, checks)

Revision ID: 20260730_0001
Revises: 20260716_0001
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260730_0001"
down_revision = "20260716_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "courses",
        sa.Column("course_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("course_code", sa.String(length=50), nullable=False),
        sa.Column("course_title", sa.String(length=300), nullable=False),
        sa.Column("program", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("course_code", name="uq_courses_course_code"),
    )

    op.create_table(
        "curriculum_objectives",
        sa.Column("objective_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("program", sa.String(length=50), nullable=False),
        sa.UniqueConstraint(
            "code", "program", name="uq_curriculum_objectives_code_program"
        ),
    )

    op.create_table(
        "curriculum_map_cells",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("objective_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=1), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.course_id"]),
        sa.ForeignKeyConstraint(
            ["objective_id"], ["curriculum_objectives.objective_id"]
        ),
        sa.UniqueConstraint(
            "course_id", "objective_id", name="uq_curriculum_map_cells_course_objective"
        ),
        sa.CheckConstraint("level IN ('I', 'E', 'D')", name="ck_curriculum_map_cells_level"),
    )

    op.create_table(
        "curriculum_alignment_checks",
        sa.Column("check_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("objective_results", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.course_id"]),
    )


def downgrade():
    op.drop_table("curriculum_alignment_checks")
    op.drop_table("curriculum_map_cells")
    op.drop_table("curriculum_objectives")
    op.drop_table("courses")
