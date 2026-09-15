"""Update the managed SME prompt for the grouped-LLM-scoring redesign.

The prompt seeded by 20260811_0002 was written for the pre-redesign
fact-extraction-only SME (extraction and scoring were separate steps).
Grouped scoring (see docs/superpowers/specs/2026-08-13-sme-dpo-scoring-design.md,
dated after that seed) has SME extract and score in one call, so that
preamble's "do not evaluate, assess... only extracted facts" instruction
directly contradicts the grouped prompt's score/justification/evidence
request sent in the same call.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

revision = "20260820_0001"
down_revision = "20260814_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SME_VERSION_ID = uuid.UUID("5534236d-59fd-4a71-9118-9f3ec9ede711")
SME_GROUPED_SCORING_PROMPT = (
    "You are an SME evaluator for Self-Paced Learning Modules. Score only "
    "the criteria and document text supplied in this request, following "
    "each criterion's scoring_rule exactly. Do not use external knowledge, "
    "the original PDF, or any content outside the supplied document_text."
)


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM prompt_versions WHERE version_id=:version_id"),
        {"version_id": str(SME_VERSION_ID)},
    ).scalar()
    if exists:
        return
    version_number = conn.execute(
        sa.text(
            "SELECT COALESCE(MAX(version_number), 0) + 1 "
            "FROM prompt_versions WHERE agent_id=:agent"
        ),
        {"agent": "sme"},
    ).scalar_one()
    conn.execute(
        sa.text(
            "UPDATE prompt_versions SET is_active=:inactive "
            "WHERE agent_id=:agent AND is_active=:active"
        ),
        {"inactive": False, "agent": "sme", "active": True},
    )
    conn.execute(
        sa.text(
            "INSERT INTO prompt_versions "
            "(version_id, agent_id, version_number, prompt_text, is_active, "
            "motivation, created_at, updated_by) VALUES "
            "(:version_id, :agent, :version_number, :prompt_text, :active, "
            ":motivation, :created_at, :updated_by)"
        ),
        {
            "version_id": str(SME_VERSION_ID),
            "agent": "sme",
            "version_number": version_number,
            "prompt_text": SME_GROUPED_SCORING_PROMPT,
            "active": True,
            "motivation": (
                "Replace fact-extraction-only preamble with one matching "
                "grouped scoring, which extracts and scores in one call"
            ),
            "created_at": datetime.now(UTC),
            "updated_by": None,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    seeded_number = conn.execute(
        sa.text(
            "SELECT version_number FROM prompt_versions "
            "WHERE version_id=:version_id AND agent_id=:agent"
        ),
        {"agent": "sme", "version_id": str(SME_VERSION_ID)},
    ).scalar()
    if seeded_number is None:
        return
    conn.execute(
        sa.text("DELETE FROM prompt_versions WHERE version_id=:version_id"),
        {"version_id": str(SME_VERSION_ID)},
    )
    later_active = conn.execute(
        sa.text(
            "SELECT 1 FROM prompt_versions WHERE agent_id=:agent "
            "AND version_number > :version_number AND is_active=:active"
        ),
        {"agent": "sme", "version_number": seeded_number, "active": True},
    ).scalar()
    if not later_active:
        conn.execute(
            sa.text(
                "UPDATE prompt_versions SET is_active=:inactive WHERE agent_id=:agent"
            ),
            {"agent": "sme", "inactive": False},
        )
        conn.execute(
            sa.text(
                "UPDATE prompt_versions SET is_active=:active WHERE version_id="
                "(SELECT version_id FROM prompt_versions WHERE agent_id=:agent "
                "ORDER BY version_number DESC LIMIT 1)"
            ),
            {"agent": "sme", "active": True},
        )
