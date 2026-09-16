"""Trim the managed GAD prompt to role/task framing only.

Revision ID: 20260829_0003
Revises: 20260829_0002
Create Date: 2026-08-29

The per-criterion "what counts" guidance now lives in
rubric_criteria.scoring_rule (Rubric Editor); the structural scaffold and
CRITICAL RULES live in server/modules/agents/gad/prompt.py. This removes
the duplicate CRITERIA / CRITICAL RULES sections from the managed prompt so
there is one editable source per concern.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

revision: str = "20260829_0003"
down_revision: str | None = "20260829_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRIMMED_GAD_PROMPT = (
    "You are a Gender and Development (GAD) fact extractor for Student "
    "Learning Materials (SLMs). Your role is to examine the provided "
    "document chunks and extract specific factual observations for each "
    "GAD criterion. Do not assign numeric scores. Do not write "
    "recommendations beyond the required per-criterion summary.\n\n"
    "TASK:\n"
    "Work only from the provided document_chunks. Do not use external "
    "knowledge, syllabus, curriculum, or reference materials as factual "
    "sources. For each of the five GAD criteria you will be given the "
    "specific counting rule to apply and the exact fields to return.\n\n"
    "OUTPUT FORMAT:\n"
    "Return a single JSON object with exactly five keys: 'gad-01', "
    "'gad-02', 'gad-03', 'gad-04', 'gad-05', and nothing else."
)

GAD_VERSION_ID = uuid.UUID("c3d4e5f6-a7b8-9012-cdef-345678901234")


def upgrade() -> None:
    conn = op.get_bind()
    op.execute(
        sa.text(
            "UPDATE prompt_versions SET is_active = :inactive "
            "WHERE agent_id = :agent_id AND is_active = :active"
        ).bindparams(inactive=False, agent_id="gad", active=True)
    )
    # Idempotent: if this exact version already exists, just re-activate it.
    existing = conn.execute(
        sa.text(
            "SELECT version_number FROM prompt_versions WHERE version_id = :id"
        ).bindparams(id=GAD_VERSION_ID)
    ).scalar()
    if existing is not None:
        op.execute(
            sa.text(
                "UPDATE prompt_versions SET is_active = :active "
                "WHERE version_id = :id"
            ).bindparams(active=True, id=GAD_VERSION_ID)
        )
        return
    current_max = (
        conn.execute(
            sa.text(
                "SELECT COALESCE(MAX(version_number), 0) FROM prompt_versions "
                "WHERE agent_id = :agent_id"
            ).bindparams(agent_id="gad")
        ).scalar()
        or 0
    )
    prompt_versions = sa.table(
        "prompt_versions",
        sa.column("version_id", sa.Uuid),
        sa.column("agent_id", sa.String),
        sa.column("version_number", sa.Integer),
        sa.column("prompt_text", sa.Text),
        sa.column("is_active", sa.Boolean),
        sa.column("motivation", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_by", sa.Uuid),
    )
    op.bulk_insert(
        prompt_versions,
        [
            {
                "version_id": GAD_VERSION_ID,
                "agent_id": "gad",
                "version_number": current_max + 1,
                "prompt_text": TRIMMED_GAD_PROMPT,
                "is_active": True,
                "motivation": (
                    "Trimmed managed GAD prompt to framing only; per-criterion "
                    "counting rules now live in rubric_criteria.scoring_rule "
                    "(dynamic GAD counting rules)"
                ),
                "created_at": datetime.utcnow(),
                "updated_by": None,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM prompt_versions "
            "WHERE agent_id = :agent_id AND version_id = :version_id"
        ).bindparams(agent_id="gad", version_id=GAD_VERSION_ID)
    )
    op.execute(
        sa.text(
            "UPDATE prompt_versions SET is_active = :active "
            "WHERE agent_id = :agent_id AND version_number = ("
            "  SELECT MAX(version_number) FROM prompt_versions "
            "  WHERE agent_id = :agent_id2)"
        ).bindparams(active=True, agent_id="gad", agent_id2="gad")
    )
