"""add program roadmap tables (program_roadmaps, roadmap_years, roadmap_courses)

Revision ID: 20260808_0001
Revises: 20260808_0000
Create Date: 2026-08-08
"""

import sqlalchemy as sa

from alembic import op

revision = "20260808_0001"
down_revision = "20260808_0000"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "program_roadmaps",
        sa.Column("roadmap_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("program", sa.String(length=50), nullable=False),
        sa.Column("specialization", sa.String(length=200), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_document_path", sa.String(length=500), nullable=True),
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
        sa.UniqueConstraint(
            "program",
            "specialization",
            "version_number",
            name="uq_program_roadmaps_program_specialization_version",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'retired')", name="ck_program_roadmaps_status"
        ),
    )

    op.create_table(
        "roadmap_years",
        sa.Column("year_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("roadmap_id", sa.Uuid(), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["roadmap_id"],
            ["program_roadmaps.roadmap_id"],
            name="fk_roadmap_years_roadmap",
        ),
        sa.UniqueConstraint(
            "roadmap_id", "year_number", "semester", name="uq_roadmap_years_position"
        ),
    )
    op.create_index(
        "idx_roadmap_years_roadmap_id", "roadmap_years", ["roadmap_id"]
    )

    op.create_table(
        "roadmap_courses",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("roadmap_id", sa.Uuid(), nullable=False),
        sa.Column("year_id", sa.Uuid(), nullable=False),
        sa.Column("course_code", sa.String(length=50), nullable=False),
        sa.Column("course_title", sa.String(length=300), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=True),
        sa.Column("course_status", sa.String(length=20), nullable=False),
        sa.Column("tech_stack", sa.Text(), nullable=True),
        sa.Column("competency_stage", sa.String(length=100), nullable=True),
        sa.Column("learning_outcomes_summary", sa.Text(), nullable=True),
        sa.Column("portfolio_project_suggestion", sa.Text(), nullable=True),
        sa.Column("relevant_certification", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(
            ["roadmap_id"],
            ["program_roadmaps.roadmap_id"],
            name="fk_roadmap_courses_roadmap",
        ),
        sa.ForeignKeyConstraint(
            ["year_id"], ["roadmap_years.year_id"], name="fk_roadmap_courses_year"
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.course_id"], name="fk_roadmap_courses_course"
        ),
        sa.CheckConstraint(
            "course_status IN ('existing', 'proposed')",
            name="ck_roadmap_courses_course_status",
        ),
    )
    op.create_index(
        "idx_roadmap_courses_roadmap_code",
        "roadmap_courses",
        ["roadmap_id", "course_code"],
    )
    op.create_index(
        "idx_roadmap_courses_year_id", "roadmap_courses", ["year_id"]
    )


def downgrade():
    op.drop_table("roadmap_courses")
    op.drop_table("roadmap_years")
    op.drop_table("program_roadmaps")
