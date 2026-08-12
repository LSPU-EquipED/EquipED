"""Seed the managed SME fact-extraction prompt."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

revision = "20260811_0002"
down_revision = "20260811_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SME_VERSION_ID = uuid.UUID("b1c2d3e4-f5a6-7890-abcd-ef1234567890")
SME_EXTRACTION_PROMPT = (
    "You are an SME fact extractor for Self-Paced Learning Modules. Extract "
    "facts only from the supplied canonical SLM text. Do not evaluate, assess, "
    "repair, infer, or use external or PDF content. Return only valid JSON "
    "containing the requested extracted facts."
)


def upgrade() -> None:
    conn = op.get_bind()
    # The UUID is fixed so retries can identify the row without relying on a
    # particular version number.  A retry must not deactivate the active row.
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
            "prompt_text": SME_EXTRACTION_PROMPT,
            "active": True,
            "motivation": "Seed fact-only SME extraction prompt",
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
