"""Read queries and response mapping for standalone syllabus alignment."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.documents.models import Document, DocumentChunk
from server.modules.syllabus_alignment.admission import require_owned_slm
from server.modules.syllabus_alignment.exceptions import SyllabusAlignmentNotFoundError
from server.modules.syllabus_alignment.models import SyllabusAlignmentRun
from server.modules.syllabus_alignment.schemas import (
    SyllabusAlignmentRunResponse,
    SyllabusAlignmentSlmItem,
    SyllabusAlignmentSlmListResponse,
    SyllabusAlignmentStats,
)
from sqlalchemy import case, func, or_


def to_run_response(
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


def get_syllabus_alignment(
    db: Any, alignment_id: uuid.UUID, requested_by: uuid.UUID
) -> SyllabusAlignmentRunResponse:
    run = db.get(SyllabusAlignmentRun, alignment_id)
    if run is None or run.requested_by != requested_by:
        raise SyllabusAlignmentNotFoundError("Alignment run not found")
    return to_run_response(db, run)


def get_current_syllabus_alignment(
    db: Any,
    *,
    slm_document_id: uuid.UUID,
    requested_by: uuid.UUID,
) -> SyllabusAlignmentRunResponse | None:
    require_owned_slm(db, slm_document_id, requested_by)
    run = (
        db.query(SyllabusAlignmentRun)
        .filter_by(
            slm_document_id=slm_document_id,
            requested_by=requested_by,
        )
        .first()
    )
    return to_run_response(db, run) if run is not None else None


def list_alignment_slms(
    db: Any,
    *,
    requested_by: uuid.UUID,
    page: int,
    page_size: int,
    search: str | None = None,
    status_filter: str | None = None,
) -> SyllabusAlignmentSlmListResponse:
    base_query = db.query(Document).filter_by(
        source_type="slm", uploaded_by=requested_by
    )

    # Compute repository-wide stats before pagination across all owned SLMs
    # Left outer join with SyllabusAlignmentRun for this requested_by
    stats_row = (
        db.query(
            func.count(Document.document_id),
            func.count(
                case(
                    (
                        (SyllabusAlignmentRun.status == "COMPLETED")
                        & (SyllabusAlignmentRun.alignment_level == "MEETS"),
                        1,
                    )
                )
            ),
            func.count(
                case(
                    (
                        (SyllabusAlignmentRun.status == "COMPLETED")
                        & (SyllabusAlignmentRun.alignment_level == "PARTIALLY_MEETS"),
                        1,
                    )
                )
            ),
            func.count(
                case(
                    (
                        (
                            (SyllabusAlignmentRun.status == "COMPLETED")
                            & (SyllabusAlignmentRun.alignment_level == "DOES_NOT_MEET")
                        )
                        | (SyllabusAlignmentRun.status == "FAILED"),
                        1,
                    )
                )
            ),
            func.count(
                case(
                    (
                        SyllabusAlignmentRun.alignment_id.is_(None)
                        | SyllabusAlignmentRun.status.in_(["QUEUED", "RUNNING"]),
                        1,
                    )
                )
            ),
        )
        .select_from(Document)
        .outerjoin(
            SyllabusAlignmentRun,
            (SyllabusAlignmentRun.slm_document_id == Document.document_id)
            & (SyllabusAlignmentRun.requested_by == requested_by),
        )
        .filter(Document.source_type == "slm", Document.uploaded_by == requested_by)
        .one()
    )
    stats = SyllabusAlignmentStats(
        total=int(stats_row[0] or 0),
        meets=int(stats_row[1] or 0),
        partially_meets=int(stats_row[2] or 0),
        needs_attention=int(stats_row[3] or 0),
        pending=int(stats_row[4] or 0),
    )

    # Apply search and status_filter to document query before pagination
    query = base_query
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.filter(
            or_(
                func.lower(Document.title).like(search_pattern),
                func.lower(Document.course_title).like(search_pattern),
                func.lower(Document.lesson_title).like(search_pattern),
                func.lower(Document.program).like(search_pattern),
                func.lower(Document.course_code).like(search_pattern),
            )
        )

    if status_filter:
        normalized_status = status_filter.strip().upper()
        query = query.outerjoin(
            SyllabusAlignmentRun,
            (SyllabusAlignmentRun.slm_document_id == Document.document_id)
            & (SyllabusAlignmentRun.requested_by == requested_by),
        )
        if normalized_status == "MEETS":
            query = query.filter(
                SyllabusAlignmentRun.status == "COMPLETED",
                SyllabusAlignmentRun.alignment_level == "MEETS",
            )
        elif normalized_status == "PARTIALLY_MEETS":
            query = query.filter(
                SyllabusAlignmentRun.status == "COMPLETED",
                SyllabusAlignmentRun.alignment_level == "PARTIALLY_MEETS",
            )
        elif normalized_status == "ATTENTION":
            query = query.filter(
                or_(
                    (SyllabusAlignmentRun.status == "COMPLETED")
                    & (SyllabusAlignmentRun.alignment_level == "DOES_NOT_MEET"),
                    SyllabusAlignmentRun.status == "FAILED",
                )
            )
        elif normalized_status == "PENDING":
            query = query.filter(
                or_(
                    SyllabusAlignmentRun.alignment_id.is_(None),
                    SyllabusAlignmentRun.status.in_(["QUEUED", "RUNNING"]),
                )
            )

    total = query.count()
    documents = (
        query.order_by(Document.uploaded_at.desc(), Document.document_id.desc())
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
                current_result=to_run_response(
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
        stats=stats,
    )


__all__ = [
    "to_run_response",
    "get_syllabus_alignment",
    "get_current_syllabus_alignment",
    "list_alignment_slms",
]
