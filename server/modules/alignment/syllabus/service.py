"""Lifecycle and persistence for standalone SLM-to-syllabus alignment."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from server.core.config import get_settings
from server.modules.alignment.syllabus.exceptions import (
    InvalidSyllabusAlignmentTargetError,
    SyllabusAlignmentNotFoundError,
)
from server.modules.alignment.syllabus.models import (
    SyllabusAlignmentLevel,
    SyllabusAlignmentRun,
    SyllabusAlignmentStatus,
)
from server.modules.alignment.syllabus.schemas import (
    SyllabusAlignmentRunResponse,
    SyllabusAlignmentSlmItem,
    SyllabusAlignmentSlmListResponse,
)
from server.modules.documents import persistence
from server.modules.documents.models import Document, DocumentChunk
from server.modules.documents.syllabus.service import is_syllabus_reference_ready
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)
_ACTIVE_STATUSES = (
    SyllabusAlignmentStatus.QUEUED.value,
    SyllabusAlignmentStatus.RUNNING.value,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _owned_slm(db: Any, document_id: uuid.UUID, owner_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if (
        document is None
        or document.source_type != "slm"
        or document.uploaded_by != owner_id
    ):
        raise SyllabusAlignmentNotFoundError("SLM document not found")
    return document


def _run_response(
    db: Any,
    run: SyllabusAlignmentRun,
    document_lookup: dict[uuid.UUID, Document] | None = None,
) -> SyllabusAlignmentRunResponse:
    slm = (
        document_lookup.get(run.slm_document_id)
        if document_lookup is not None
        else db.get(Document, run.slm_document_id)
    )
    syllabus = (
        document_lookup.get(run.syllabus_document_id)
        if document_lookup is not None
        else db.get(Document, run.syllabus_document_id)
    )
    return SyllabusAlignmentRunResponse(
        alignment_id=run.alignment_id,
        slm_document_id=run.slm_document_id,
        slm_title=slm.title if slm else None,
        syllabus_document_id=run.syllabus_document_id,
        syllabus_title=syllabus.title if syllabus else None,
        requested_by=run.requested_by,
        status=run.status,
        alignment_level=run.alignment_level,
        justification=run.justification,
        alignment_artifact=run.alignment_artifact,
        model_name=run.model_name,
        provenance=run.provenance,
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        updated_at=run.updated_at,
    )


def create_syllabus_alignment(
    db: Any,
    *,
    slm_document_id: uuid.UUID,
    syllabus_document_id: uuid.UUID,
    requested_by: uuid.UUID,
    background_tasks: Any,
) -> SyllabusAlignmentRunResponse:
    """Validate direct inputs, create an independent run, and queue execution."""
    slm = _owned_slm(db, slm_document_id, requested_by)
    chunk_count = (
        db.query(func.count(DocumentChunk.chunk_id))
        .filter(DocumentChunk.document_id == slm.document_id)
        .scalar()
    )
    if slm.processing_status != "PROCESSED" or not chunk_count:
        raise InvalidSyllabusAlignmentTargetError(
            "The selected SLM must finish processing before alignment."
        )

    syllabus = db.get(Document, syllabus_document_id)
    if syllabus is None or syllabus.source_type != "syllabus":
        raise InvalidSyllabusAlignmentTargetError(
            "Select a syllabus from the shared Reference Library."
        )
    ready, _content_count = is_syllabus_reference_ready(syllabus, db)
    if not ready:
        raise InvalidSyllabusAlignmentTargetError(
            "The selected syllabus is not retrieval-ready. Ask an admin to "
            "finish processing or rebuild its embeddings."
        )

    existing = (
        db.query(SyllabusAlignmentRun)
        .filter(
            SyllabusAlignmentRun.slm_document_id == slm_document_id,
            SyllabusAlignmentRun.requested_by == requested_by,
        )
        .with_for_update()
        .first()
    )
    if existing is not None and existing.status in _ACTIVE_STATUSES:
        return _run_response(db, existing)

    model_name = get_settings().get_agent_model("sme")
    now = _now()
    if existing is None:
        run = SyllabusAlignmentRun(
            alignment_id=uuid.uuid4(),
            slm_document_id=slm_document_id,
            syllabus_document_id=syllabus_document_id,
            requested_by=requested_by,
            status=SyllabusAlignmentStatus.QUEUED.value,
            model_name=model_name,
            provenance={"agent_configuration": "sme", "requested_model": model_name},
            created_at=now,
            updated_at=now,
        )
        db.add(run)
    else:
        run = existing
        run.syllabus_document_id = syllabus_document_id
        run.status = SyllabusAlignmentStatus.QUEUED.value
        run.alignment_level = None
        run.justification = None
        run.alignment_artifact = None
        run.model_name = model_name
        run.provenance = {
            "agent_configuration": "sme",
            "requested_model": model_name,
        }
        run.error_message = None
        run.created_at = now
        run.started_at = None
        run.completed_at = None
        run.updated_at = now
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        active = (
            db.query(SyllabusAlignmentRun)
            .filter(
                SyllabusAlignmentRun.slm_document_id == slm_document_id,
                SyllabusAlignmentRun.requested_by == requested_by,
            )
            .first()
        )
        if active is None:
            raise
        return _run_response(db, active)
    db.refresh(run)
    background_tasks.add_task(run_syllabus_alignment_job, run.alignment_id)
    return _run_response(db, run)


def run_syllabus_alignment_job(alignment_id: uuid.UUID) -> None:
    """Execute one persisted run without touching evaluation or agent results."""
    from server.core.database import get_session_factory
    from server.core.llm import get_llm_client_for_agent
    from server.modules.alignment.syllabus import evaluator as syllabus_alignment

    session = get_session_factory()()
    try:
        claimed_at = _now()
        claimed = (
            session.query(SyllabusAlignmentRun)
            .filter(
                SyllabusAlignmentRun.alignment_id == alignment_id,
                SyllabusAlignmentRun.status == SyllabusAlignmentStatus.QUEUED.value,
            )
            .update(
                {
                    SyllabusAlignmentRun.status: SyllabusAlignmentStatus.RUNNING.value,
                    SyllabusAlignmentRun.started_at: claimed_at,
                    SyllabusAlignmentRun.updated_at: claimed_at,
                },
                synchronize_session=False,
            )
        )
        session.commit()
        if claimed != 1:
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
        run.model_name = getattr(client, "model", run.model_name)
        result = syllabus_alignment.evaluate(
            client,
            chunk_infos,
            run.syllabus_document_id,
            syllabus_contents,
        )
        run.justification = str(result.get("statement") or "").strip()
        run.alignment_artifact = result
        run.completed_at = _now()
        run.updated_at = run.completed_at
        level = str(result.get("status", "UNAVAILABLE"))
        if level == SyllabusAlignmentLevel.UNAVAILABLE.value:
            run.status = SyllabusAlignmentStatus.FAILED.value
            run.alignment_level = SyllabusAlignmentLevel.UNAVAILABLE.value
            run.error_message = (
                run.justification or "Alignment analysis was unavailable."
            )
        else:
            run.status = SyllabusAlignmentStatus.COMPLETED.value
            run.alignment_level = level
            run.error_message = None
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Standalone syllabus alignment failed")
        failed = session.get(SyllabusAlignmentRun, alignment_id)
        if failed is not None:
            failed.status = SyllabusAlignmentStatus.FAILED.value
            failed.alignment_level = SyllabusAlignmentLevel.UNAVAILABLE.value
            failed.justification = (
                "Syllabus alignment could not be completed. You can retry this SLM."
            )
            failed.error_message = (
                "Syllabus alignment could not be completed because the alignment "
                "service failed. You can retry this SLM."
            )
            failed.completed_at = _now()
            failed.updated_at = failed.completed_at
            session.commit()
    finally:
        session.close()


def get_syllabus_alignment(
    db: Any, alignment_id: uuid.UUID, requested_by: uuid.UUID
) -> SyllabusAlignmentRunResponse:
    run = db.get(SyllabusAlignmentRun, alignment_id)
    if run is None or run.requested_by != requested_by:
        raise SyllabusAlignmentNotFoundError("Alignment run not found")
    return _run_response(db, run)


def get_current_syllabus_alignment(
    db: Any,
    *,
    slm_document_id: uuid.UUID,
    requested_by: uuid.UUID,
) -> SyllabusAlignmentRunResponse | None:
    _owned_slm(db, slm_document_id, requested_by)
    run = (
        db.query(SyllabusAlignmentRun)
        .filter_by(
            slm_document_id=slm_document_id,
            requested_by=requested_by,
        )
        .first()
    )
    return _run_response(db, run) if run is not None else None


def list_alignment_slms(
    db: Any, *, requested_by: uuid.UUID, page: int, page_size: int
) -> SyllabusAlignmentSlmListResponse:
    query = db.query(Document).filter_by(source_type="slm", uploaded_by=requested_by)
    total = query.count()
    documents = (
        query.order_by(Document.uploaded_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    document_ids = [document.document_id for document in documents]
    chunk_counts: dict[uuid.UUID, int] = {}
    latest: dict[uuid.UUID, SyllabusAlignmentRun] = {}
    if document_ids:
        chunk_counts = dict(
            db.query(DocumentChunk.document_id, func.count(DocumentChunk.chunk_id))
            .filter(DocumentChunk.document_id.in_(document_ids))
            .group_by(DocumentChunk.document_id)
            .all()
        )
        for run in db.query(SyllabusAlignmentRun).filter(
            SyllabusAlignmentRun.requested_by == requested_by,
            SyllabusAlignmentRun.slm_document_id.in_(document_ids),
        ):
            latest[run.slm_document_id] = run
        syllabus_ids = {run.syllabus_document_id for run in latest.values()}
        syllabus_documents = (
            db.query(Document).filter(Document.document_id.in_(syllabus_ids)).all()
            if syllabus_ids
            else []
        )
        document_lookup = {document.document_id: document for document in documents}
        document_lookup.update(
            {document.document_id: document for document in syllabus_documents}
        )
    else:
        document_lookup = {}
    return SyllabusAlignmentSlmListResponse(
        items=[
            SyllabusAlignmentSlmItem(
                document_id=document.document_id,
                title=document.title,
                course_title=document.course_title,
                lesson_title=document.lesson_title,
                program=document.program,
                course_code=document.course_code,
                processing_status=document.processing_status,
                uploaded_at=document.uploaded_at,
                evaluation_available=(
                    document.processing_status == "PROCESSED"
                    and chunk_counts.get(document.document_id, 0) > 0
                ),
                current_result=_run_response(
                    db, latest[document.document_id], document_lookup
                )
                if document.document_id in latest
                else None,
            )
            for document in documents
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def fail_interrupted_syllabus_alignments(session_factory: Any) -> int:
    """Fail active BackgroundTasks runs after a process restart."""
    session = session_factory()
    try:
        now = _now()
        rows = (
            session.query(SyllabusAlignmentRun)
            .filter(SyllabusAlignmentRun.status.in_(_ACTIVE_STATUSES))
            .all()
        )
        for run in rows:
            run.status = SyllabusAlignmentStatus.FAILED.value
            run.alignment_level = SyllabusAlignmentLevel.UNAVAILABLE.value
            run.justification = (
                "The alignment run was interrupted by an application restart. "
                "Start a new run to retry."
            )
            run.error_message = (
                "Background alignment interrupted by application restart."
            )
            run.completed_at = now
            run.updated_at = now
        session.commit()
        return len(rows)
    finally:
        session.close()


__all__ = [
    "create_syllabus_alignment",
    "fail_interrupted_syllabus_alignments",
    "get_current_syllabus_alignment",
    "get_syllabus_alignment",
    "list_alignment_slms",
    "run_syllabus_alignment_job",
]
