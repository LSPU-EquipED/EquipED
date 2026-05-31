"""add rubric tables for relational rubric storage

Revision ID: 20260527_0014
Revises: 20260523_0013
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260527_0014"
down_revision = "20260523_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rubric_sets",
        sa.Column("rubric_set_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("agent_id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agent_id", "version_number", name="uq_rubric_sets_agent_version"),
    )

    op.create_table(
        "rubric_domains",
        sa.Column("rubric_domain_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("rubric_set_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["rubric_set_id"], ["rubric_sets.rubric_set_id"]),
        sa.UniqueConstraint("rubric_set_id", "code", name="uq_rubric_domains_set_code"),
    )

    op.create_table(
        "rubric_criteria",
        sa.Column("rubric_criterion_id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("rubric_domain_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["rubric_domain_id"], ["rubric_domains.rubric_domain_id"]),
        sa.UniqueConstraint("rubric_domain_id", "criterion_code", name="uq_rubric_criteria_domain_code"),
    )


def downgrade():
    op.drop_table("rubric_criteria")
    op.drop_table("rubric_domains")
    op.drop_table("rubric_sets")
