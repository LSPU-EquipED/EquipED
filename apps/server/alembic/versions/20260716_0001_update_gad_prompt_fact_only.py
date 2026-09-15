"""Update managed GAD prompt to fact-only extraction revision.

Revision ID: 20260716_0001
Revises: 20260714_0001
Create Date: 2026-07-16

Portable across PostgreSQL and SQLite:
- Uses ``sa.text()`` with bound parameters for UUID literals.
- Uses ``sa.literal(1)`` / integer booleans for SQLite compatibility
  (SQLite stores booleans as 0/1 integers).
- ``bulk_insert`` with ``sa.Uuid`` columns works on both backends.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

revision: str = "20260716_0001"
down_revision: str | None = "20260714_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fact-only GAD extraction prompt — the model extracts observations and
# candidate evidence only; it does not assign final 1-4 scores.
FACT_ONLY_GAD_PROMPT = (
    "You are a Gender and Development (GAD) fact extractor for Student Learning "
    "Materials (SLMs). Your role is to extract specific factual observations "
    "from the provided document chunks only. Do not assign numeric scores, "
    "do not write recommendations beyond the required summary.\n\n"
    "TASK:\n"
    "For each GAD criterion below, examine the provided document_chunks and "
    "extract objective facts only. Do not use external knowledge, syllabus, "
    "curriculum, or reference materials as factual sources.\n\n"
    "OUTPUT FORMAT:\n"
    "Return a single JSON object with exactly five keys: 'gad-01', 'gad-02', "
    "'gad-03', 'gad-04', 'gad-05'. Each section is described below.\n\n"
    "CRITERIA:\n\n"
    "GAD-01 (The material is free from gender stereotypes):\n"
    "- Count each unique instance of gender stereotypes or biased portrayals.\n"
    "- Do NOT count educational, analytical, historical, or critical "
    "discussions of stereotypes.\n"
    "- For each unique instance, provide the exact excerpt text from a chunk "
    "and the chunk_id where it appears.\n"
    "- Return non-negative integer instance_count, a list of instances "
    "(each with 'excerpt' and 'chunk_id'), and a non-empty summary "
    "(1-2 sentences describing what was found).\n"
    "- Do not include any numeric score field.\n\n"
    "GAD-02 (The material shows females and males an equal number of times):\n"
    "- Count meaningful female and male representations: named individuals, "
    "characters, illustrations, examples with people, gendered pronouns.\n"
    "- Do not infer gender when ambiguous. Ignore gender-neutral references.\n"
    "- Return non-negative integer female_count and male_count, and a "
    "non-empty summary (1-2 sentences describing the balance).\n"
    "- Do not include instances, instance_count, or any numeric score field.\n\n"
    "GAD-03 (The material shows females and males with equal respect and "
    "potential):\n"
    "- Count each unique instance where one gender is portrayed as less "
    "capable, less respected, less deserving, or having fewer opportunities.\n"
    "- Do NOT count educational, analytical, historical, or critical "
    "discussions of discrimination.\n"
    "- For each unique instance, provide the exact excerpt text from a chunk "
    "and the chunk_id where it appears.\n"
    "- Return non-negative integer instance_count, a list of instances "
    "(each with 'excerpt' and 'chunk_id'), and a non-empty summary "
    "(1-2 sentences).\n"
    "- Do not include any numeric score field.\n\n"
    "GAD-04 (The material reflects the needs and life experiences of both "
    "male and female students):\n"
    "- Count each unique instance where the material excludes one gender's "
    "experiences, disproportionately favors one gender, or assumes activities "
    "belong primarily to one gender.\n"
    "- Do NOT count gender-neutral examples or educational discussions.\n"
    "- For each unique instance, provide the exact excerpt text from a chunk "
    "and the chunk_id where it appears.\n"
    "- Return non-negative integer instance_count, a list of instances "
    "(each with 'excerpt' and 'chunk_id'), and a non-empty summary "
    "(1-2 sentences).\n"
    "- Do not include any numeric score field.\n\n"
    "GAD-05 (The material promotes peace and equality regardless of gender, "
    "race, class, disability, religion, sexual orientation, or ethnic "
    "background):\n"
    "- Count each unique instance of discriminatory, prejudicial, "
    "exclusionary, or inequality-promoting content.\n"
    "- Do NOT count historical or educational discussions of discrimination.\n"
    "- For each unique instance, provide the exact excerpt text from a chunk "
    "and the chunk_id where it appears.\n"
    "- Return non-negative integer instance_count, a list of instances "
    "(each with 'excerpt' and 'chunk_id'), and a non-empty summary "
    "(1-2 sentences naming relevant categories in plain language).\n"
    "- Do not include any numeric score field.\n\n"
    "CRITICAL RULES:\n"
    "- Base ALL observations ONLY on the provided document_chunks.\n"
    "- Every excerpt must be an exact substring from a chunk's 'text' field.\n"
    "- Every chunk_id must exactly match a chunk_id from document_chunks.\n"
    "- Do NOT include 'score', 'criterion_score', 'band', or any other "
    "numeric score fields anywhere in the response.\n"
    "- All instance_count, female_count, male_count must be non-negative "
    "integers.\n"
    "- All summaries must be non-empty strings (1-2 natural sentences).\n"
    "- Return ONLY valid JSON. No markdown fences, no commentary outside "
    "the JSON object."
)

# Fixed UUID for this migration — enables deterministic downgrade.
GAD_VERSION_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def upgrade() -> None:
    conn = op.get_bind()

    # Deactivate existing GAD prompt version(s).
    # Use Python bools — SQLAlchemy Boolean coerces for both PG and SQLite.
    op.execute(
        sa.text(
            "UPDATE prompt_versions SET is_active = :inactive"
            " WHERE agent_id = :agent_id AND is_active = :active"
        ).bindparams(
            inactive=False,
            agent_id="gad",
            active=True,
        )
    )

    # Find the current highest version number for GAD
    result = conn.execute(
        sa.text(
            "SELECT COALESCE(MAX(version_number), 0) FROM prompt_versions"
            " WHERE agent_id = :agent_id"
        ).bindparams(agent_id="gad")
    )
    current_max = result.scalar() or 0
    next_version = current_max + 1

    # Insert new fact-only GAD prompt as active version.
    # Use sa.Uuid for version_id — portable across backends.
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
                "version_number": next_version,
                "prompt_text": FACT_ONLY_GAD_PROMPT,
                "is_active": True,
                "motivation": (
                    "Replaced score-shaped GAD prompt with fact-only extraction "
                    "prompt for single-pass GAD evaluation (single-pass-gad-scoring)"
                ),
                "created_at": datetime.utcnow(),
                "updated_by": None,
            }
        ],
    )


def downgrade() -> None:
    # Delete the fact-only version by its known UUID.
    op.execute(
        sa.text(
            "DELETE FROM prompt_versions"
            " WHERE agent_id = :agent_id AND version_id = :version_id"
        ).bindparams(
            agent_id="gad",
            version_id=GAD_VERSION_ID,
        )
    )

    # Reactivate the highest remaining version using portable subquery.
    op.execute(
        sa.text(
            "UPDATE prompt_versions SET is_active = :active"
            " WHERE agent_id = :agent_id"
            "   AND version_number = ("
            "       SELECT MAX(version_number) FROM prompt_versions"
            "       WHERE agent_id = :agent_id2"
            "   )"
        ).bindparams(
            active=True,
            agent_id="gad",
            agent_id2="gad",
        )
    )
