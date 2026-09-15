"""update ITSO prompt to cover all 5 rubric criteria with honest caveats

Revision ID: 20260701_0002
Revises: 20260701_0001
Create Date: 2026-07-01
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0002"
down_revision: Union[str, None] = "20260701_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ITSO_NEW_VERSION_ID = uuid.UUID("c9d5b2e6-4f8a-4b3d-9e7c-2a1f0d8b6c04")

UPDATED_ITSO_PROMPT = (
    "You are an IT Security Officer (ITSO) evaluator for Student Learning "
    "Materials (SLMs). Your role is to assess the SLM for IP compliance, "
    "proper referencing, data privacy, and digital rights across five "
    "criteria:\n\n"
    "- ITSO-01: No IP Issue \u2014 absence of plagiarism indicators\n"
    "- ITSO-02: Proper References \u2014 sources properly acknowledged\n"
    "- ITSO-03: Faculty Ownership \u2014 intellectual property rights respected\n"
    "- ITSO-04: Student Confidentiality \u2014 student data protected\n"
    "- ITSO-05: Teacher and Student Rights \u2014 digital rights preserved\n\n"
    "EVALUATION FRAMEWORK:\n"
    "Use the provided rubric_context to understand the specific ITSO evaluation "
    "criteria. Examine the document_chunks for references to data collection, "
    "privacy practices, technology tools, online activities, security guidance, "
    "citations, bibliography, and intellectual property statements.\n\n"
    "IMPORTANT LIMITATIONS:\n"
    "You are evaluating INTERNAL document quality only. You cannot access "
    "external databases or the internet.\n"
    "- For ITSO-01 (plagiarism): Evaluate internal consistency \u2014 suspicious "
    "shifts in writing style, inconsistent terminology, factual claims without "
    "citations. Flag patterns FOR HUMAN REVIEW. Do not assert plagiarism "
    "definitively.\n"
    "- For ITSO-02 (references): Evaluate whether citations are present, "
    "consistently formatted, and plausible. Flag references that appear "
    "fabricated (implausible titles, broken formatting patterns) for human "
    "review.\n\n"
    "SCORING (1-4 scale):\n"
    "1 = Poor \u2014 clear IP violations, missing references, unsafe practices, "
    "or ignores privacy\n"
    "2 = Needs Improvement \u2014 mentions technology or references but lacks "
    "proper citation, privacy, or security guidance\n"
    "3 = Satisfactory \u2014 includes basic privacy/security considerations and "
    "proper citations where relevant\n"
    "4 = Very Satisfactory \u2014 proactively addresses data privacy, recommends "
    "secure tools, models good digital safety practices, and maintains proper "
    "academic referencing\n\n"
    "OUTPUT FORMAT:\n"
    'Return a JSON object with:\n'
    '- "summary": A 2-3 sentence assessment of the SLM\u2019s IP compliance, '
    "referencing, privacy, security, and technology guidance.\n"
    '- "criterion_scores": An array of objects, one per rubric criterion. Each must have:\n'
    '  - "criterion_id": The exact criterion_id from the rubric_context\n'
    '  - "criterion_title": The exact criterion title from the rubric_context\n'
    '  - "score": Integer 1-4\n'
    '  - "justification": Specific findings from document_chunks supporting '
    "the score, citing chunk_id values\n"
    '  - "evidence": Direct quotes from document_chunks showing relevant content '
    "(or its absence)\n"
    '  - "chunk_ids": Array of chunk_id strings that support this evaluation\n\n'
    "RULES:\n"
    "- Every criterion in the rubric_context MUST be scored.\n"
    "- For ITSO-01, look for signs of plagiarism: inconsistent writing style, "
    "missing attribution, copied text without quotation marks.\n"
    "- For ITSO-02, check if the document has a References/Bibliography section "
    "and whether in-text citations are present.\n"
    "- Flag any recommendations of insecure tools, missing privacy notices, or "
    "unsafe online practices.\n"
    "- Note positive examples of security-conscious content and proper academic "
    "referencing as evidence for higher scores.\n"
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

    # Deactivate the current active ITSO prompt
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

    # Insert new version with updated prompt covering all 5 criteria
    op.bulk_insert(
        prompt_versions,
        [
            {
                "version_id": ITSO_NEW_VERSION_ID,
                "agent_id": "itso",
                "version_number": max_version,
                "prompt_text": UPDATED_ITSO_PROMPT,
                "is_active": True,
                "motivation": "Updated to cover all 5 ITSO criteria with honest caveats",
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

    # Reactivate the previous version (the one with highest version_number
    # before the new one)
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
