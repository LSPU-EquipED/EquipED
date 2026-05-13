"""add agents-module tables

Revision ID: 20260513_0005
Revises: 20260511_0004
Create Date: 2026-05-13 00:05:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260513_0005"
down_revision = "20260511_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.String(length=50), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("motivation", sa.Text(), nullable=True),
        sa.Column(
            "preference_ids",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("version_id"),
        sa.UniqueConstraint(
            "agent_id",
            "version_number",
            name="uq_prompt_versions_agent_version",
        ),
    )
    op.create_index(
        "idx_prompts_agent_active",
        "prompt_versions",
        ["agent_id", "is_active"],
    )

    op.create_table(
        "agent_results",
        sa.Column("agent_result_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("processing_seconds", sa.Float(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluation_jobs.evaluation_id"]),
        sa.PrimaryKeyConstraint("agent_result_id"),
    )

    op.create_table(
        "criterion_scores",
        sa.Column("criterion_score_id", sa.Uuid(), nullable=False),
        sa.Column("agent_result_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.String(length=100), nullable=False),
        sa.Column("criterion_title", sa.String(length=300), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("chunk_ids", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("score BETWEEN 1 AND 4", name="ck_criterion_scores_score_range"),
        sa.ForeignKeyConstraint(["agent_result_id"], ["agent_results.agent_result_id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluation_jobs.evaluation_id"]),
        sa.PrimaryKeyConstraint("criterion_score_id"),
    )

    op.create_table(
        "evaluation_flags",
        sa.Column("evaluation_flag_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("agent_result_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_score_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("criterion_id", sa.String(length=100), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["agent_result_id"], ["agent_results.agent_result_id"]),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.chunk_id"]),
        sa.ForeignKeyConstraint(["criterion_score_id"], ["criterion_scores.criterion_score_id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluation_jobs.evaluation_id"]),
        sa.PrimaryKeyConstraint("evaluation_flag_id"),
    )


def downgrade() -> None:
    op.drop_table("evaluation_flags")
    op.drop_table("criterion_scores")
    op.drop_table("agent_results")
    op.drop_index("idx_prompts_agent_active", table_name="prompt_versions")
    op.drop_table("prompt_versions")
