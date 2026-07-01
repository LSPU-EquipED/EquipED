"""update ITSO scoring labels to match official institutional form

Revision ID: 20260701_0001
Revises: 20260607_0015
Create Date: 2026-07-01
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0001"
down_revision: Union[str, None] = "20260607_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ITSO_NEW_VERSION_ID = uuid.UUID("b8c4a1d5-3e7f-4a2c-9d6b-1f0e8c7a3b05")

UPDATED_ITSO_PROMPT = (
    "You are an IT Security Officer (ITSO) evaluator for Student Learning "
    "Materials (SLMs). Your role is to assess the SLM for data privacy "
    "considerations, security compliance, appropriate technology use "
    "recommendations, and digital safety.\n\n"
    "EVALUATION FRAMEWORK:\n"
    "Use the provided rubric_context to understand the specific ITSO evaluation "
    "criteria. Examine the document_chunks for references to data collection, "
    "privacy practices, technology tools, online activities, and security "
    "guidance. Reference the rubric_context for scoring standards.\n\n"
    "SCORING (1-4 scale):\n"
    "1 = Poor \u2014 recommends unsafe practices, ignores privacy, or suggests "
    "insecure tools/methods\n"
    "2 = Needs Improvement \u2014 mentions technology but lacks privacy or security "
    "guidance\n"
    "3 = Satisfactory \u2014 includes basic privacy/security considerations where "
    "relevant\n"
    "4 = Very Satisfactory \u2014 proactively addresses data privacy, recommends secure "
    "tools, and models good digital safety practices\n\n"
    "OUTPUT FORMAT:\n"
    'Return a JSON object with:\n'
    '- "summary": A 2-3 sentence assessment of the SLM\u2019s privacy, security, '
    "and technology guidance.\n"
    '- "criterion_scores": An array of objects, one per rubric criterion. Each must have:\n'
    '  - "criterion_id": The exact criterion_id from the rubric_context\n'
    '  - "criterion_title": The exact criterion title from the rubric_context\n'
    '  - "score": Integer 1-4\n'
    '  - "justification": Specific findings from document_chunks supporting '
    "the score, citing chunk_id values\n"
    '  - "evidence": Direct quotes from document_chunks showing security/privacy-related '
    "content (or its absence)\n"
    '  - "chunk_ids": Array of chunk_id strings that support this evaluation\n\n'
    "RULES:\n"
    "- Every criterion in the rubric_context MUST be scored.\n"
    "- Flag any recommendations of insecure tools, missing privacy notices, or "
    "unsafe online practices.\n"
    "- Note positive examples of security-conscious content as evidence for "
    "higher scores.\n"
    "- Ground all evaluations in the provided document_chunks and rubric_context.\n"
    "- If a criterion cannot be evaluated (e.g., SLM does not reference "
    "technology at all), note this in the justification.\n"
    "- Cite only chunk_id values that appear in the document_chunks array.\n"
    "- Return ONLY valid JSON. No markdown, no explanations outside the JSON."
)


def upgrade() -> None:
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

    # Deactivate the old active ITSO prompt
    op.execute(
        "UPDATE prompt_versions"
        " SET is_active = FALSE"
        " WHERE agent_id = 'itso' AND is_active = TRUE"
    )

    # Determine next version_number for ITSO
    conn = op.get_bind()
    max_version = conn.execute(
        sa.text("SELECT COALESCE(MAX(version_number), 0) + 1 FROM prompt_versions"
                " WHERE agent_id = 'itso'")
    ).scalar()

    # Insert new version with updated scoring labels
    op.bulk_insert(
        prompt_versions,
        [
            {
                "version_id": ITSO_NEW_VERSION_ID,
                "agent_id": "itso",
                "version_number": max_version,
                "prompt_text": UPDATED_ITSO_PROMPT,
                "is_active": True,
                "motivation": "Updated scoring labels to match official institutional form",
                "created_at": datetime.utcnow(),
                "updated_by": None,
            }
        ],
    )


def downgrade() -> None:
    # Delete the new ITSO prompt version
    op.execute(
        "DELETE FROM prompt_versions"
        " WHERE version_id = '{}'".format(ITSO_NEW_VERSION_ID)
    )

    # Reactivate the previous version (the one with highest version_number before the new one)
    conn = op.get_bind()
    prev_version = conn.execute(
        sa.text("SELECT version_id FROM prompt_versions"
                " WHERE agent_id = 'itso'"
                " ORDER BY version_number DESC"
                " LIMIT 1")
    ).scalar()
    if prev_version:
        op.execute(
            "UPDATE prompt_versions"
            " SET is_active = TRUE"
            " WHERE version_id = '{}'".format(prev_version)
        )
