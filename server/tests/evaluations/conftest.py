"""Shared fixtures and helpers for evaluations module tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from server.modules.admin.models import PromptVersion
from server.modules.documents.models import Document, DocumentChunk
from server.tests.rubrics.helpers import seed_all_rubrics

_seed_all_rubrics = seed_all_rubrics


def _add_document(
    db_session,
    *,
    owner_id,
    source_type: str,
    processing_status: str = "PROCESSED",
    with_chunks: bool = True,
    chroma_stored: bool = True,
):
    """Create a Document and optional chunk in the test database."""
    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title=f"{source_type} doc",
            program="BSCS",
            source_type=source_type,
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=owner_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status=processing_status,
        )
    )
    if with_chunks:
        db_session.add(
            DocumentChunk(
                chunk_id=uuid4(),
                document_id=document_id,
                source_type=source_type,
                agent_domain="all",
                page_number=1,
                text=f"chunk for {source_type}",
                token_count=4,
                is_ocr=False,
                chroma_stored=chroma_stored,
            )
        )
    db_session.commit()
    return document_id


def _seed_active_prompts(db_session) -> None:
    """Insert active PromptVersion rows for all four agent domains."""
    for agent_id in ["sme", "coordinator", "gad", "itso"]:
        db_session.add(
            PromptVersion(
                agent_id=agent_id,
                version_number=1,
                prompt_text=f"{agent_id} prompt",
                is_active=True,
            )
        )
    db_session.commit()
