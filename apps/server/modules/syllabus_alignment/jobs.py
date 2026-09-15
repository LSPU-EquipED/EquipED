"""Background jobs and startup recovery for standalone syllabus alignment."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from server.modules.documents import persistence
from server.modules.syllabus_alignment.models import (
    SyllabusAlignmentRun,
)
from server.modules.syllabus_alignment.repository import (
    claim_queued_run_cas,
    mark_interrupted_runs_failed,
    mark_run_completed,
    mark_run_failed,
)

logger = logging.getLogger(__name__)


def run_syllabus_alignment_job(alignment_id: uuid.UUID) -> None:
    """Execute one persisted run without touching evaluation or agent results."""
    from server.core.database import get_session_factory
    from server.core.llm import get_llm_client_for_agent
    from server.modules.syllabus_alignment import evaluator as syllabus_alignment

    session = get_session_factory()()
    try:
        if not claim_queued_run_cas(session, alignment_id):
            return
        run = session.get(SyllabusAlignmentRun, alignment_id)
        if run is None:
            return

        # The documents service is the canonical source of deterministic chunk ordering.
        chunks = [
            chunk
            for chunk in persistence.get_document_chunks(
                run.slm_document_id, db=session
            )
            if chunk.source_type == "slm"
        ]
        chunk_infos = [
            {
                "chunk_id": str(chunk.chunk_id),
                "page_number": chunk.page_number,
                "text": chunk.text,
            }
            for chunk in chunks
            if chunk.text
        ]
        syllabus_chunks = [
            chunk
            for chunk in persistence.get_document_chunks(
                run.syllabus_document_id, db=session
            )
            if chunk.section_ref
            and chunk.section_ref.startswith("syllabus_course_content:")
        ]
        syllabus_contents = [
            {
                "chunk_id": str(chunk.chunk_id),
                "content_ref": str(chunk.section_ref).split(":", 1)[-1],
                "content_text": chunk.text,
                "page_number": chunk.page_number,
            }
            for chunk in syllabus_chunks
            if chunk.text
        ]
        client = get_llm_client_for_agent("sme")
        model_name = getattr(client, "model", run.model_name)
        result = syllabus_alignment.evaluate(
            client,
            chunk_infos,
            run.syllabus_document_id,
            syllabus_contents,
        )
        mark_run_completed(
            session,
            alignment_id,
            model_name=model_name,
            result=result,
        )
    except Exception:
        session.rollback()
        logger.exception("Standalone syllabus alignment failed")
        mark_run_failed(
            session,
            alignment_id,
            error_message=(
                "Syllabus alignment could not be completed because the alignment "
                "service failed. You can retry this SLM."
            ),
            justification=(
                "Syllabus alignment could not be completed. You can retry this SLM."
            ),
        )
    finally:
        session.close()


def fail_interrupted_syllabus_alignments(session_factory: Any) -> int:
    """Fail active BackgroundTasks runs after a process restart."""
    session = session_factory()
    try:
        return mark_interrupted_runs_failed(session)
    finally:
        session.close()


__all__ = [
    "run_syllabus_alignment_job",
    "fail_interrupted_syllabus_alignments",
]
