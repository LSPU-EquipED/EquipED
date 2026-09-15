"""Document upload lifecycle and background processing orchestration."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from server.core.config import get_settings
from server.core.database import get_session_factory

from . import paths, persistence
from .exceptions import (
    ForbiddenUploadError,
    UnsupportedFileTypeError,
)
from .journaling import (
    _cleanup_failed_upload,
    _create_upload_marker,
    _remove_upload_marker,
)
from .metadata import canonicalize_supported_program
from .models import VALID_POLICY_AREAS, Document
from .processing import _process_uploaded_document
from .schemas import (
    SOURCE_TYPES,
    DocumentUploadResponse,
)

logger = logging.getLogger(__name__)

# Restricted source types that only admins can upload
_ADMIN_ONLY_SOURCE_TYPES = {
    "syllabus",
    "curriculum",
    "policy",
    "rubric_sme",
    "rubric_coord",
    "rubric_gad",
    "rubric_itso",
}


def create_document(
    file: UploadFile,
    source_type: str,
    title: str,
    course_title: str | None,
    lesson_title: str | None,
    program: str | None,
    uploaded_by: uuid.UUID,
    user_role: str = "faculty",
    policy_area: str | None = None,
    db: Any | None = None,
) -> DocumentUploadResponse:
    """Persist an upload and run Layer-1 ingestion."""

    canonical_program = _validate_upload(
        file, source_type, program, user_role, policy_area=policy_area
    )
    paths.UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    runtime_db = db
    runtime_session = None
    if runtime_db is None and get_settings().database_configured:
        runtime_session = get_session_factory()()
        runtime_db = runtime_session

    if runtime_db is not None and source_type == "slm":
        from .models import UserDocument

        doc_query = runtime_db.query(Document).filter(
            Document.source_type == "slm",
            Document.title.ilike(title.strip()),
            Document.processing_status == "PROCESSED",
        )
        if canonical_program:
            doc_query = doc_query.filter(Document.program == canonical_program)
        existing_doc = doc_query.order_by(Document.uploaded_at.desc()).first()
        if existing_doc is not None:
            from server.modules.synthesis.models import MonitoringMatrix

            matrix = (
                runtime_db.query(MonitoringMatrix)
                .filter_by(document_id=existing_doc.document_id)
                .first()
            )
            is_completed = False
            if matrix is not None:
                domain_count = len(matrix.domain_scores_json or {})
                if matrix.evaluation_status == "COMPLETED" or domain_count >= 4:
                    is_completed = True

            if not is_completed:
                user_link = (
                    runtime_db.query(UserDocument)
                    .filter_by(
                        user_id=uploaded_by, document_id=existing_doc.document_id
                    )
                    .first()
                )
                if user_link is None:
                    runtime_db.add(
                        UserDocument(
                            user_id=uploaded_by,
                            document_id=existing_doc.document_id,
                        )
                    )
                    runtime_db.commit()

                logger.info(
                    "Linked canonical SLM document_id=%s to user_id=%s storage",
                    existing_doc.document_id,
                    uploaded_by,
                )
                return DocumentUploadResponse(
                    document_id=existing_doc.document_id,
                    title=existing_doc.title,
                    course_title=existing_doc.course_title,
                    lesson_title=existing_doc.lesson_title,
                    source_type=existing_doc.source_type,
                    policy_area=existing_doc.policy_area,
                    processing_status=existing_doc.processing_status,
                    academic_year=existing_doc.academic_year,
                    course_code=existing_doc.course_code,
                    structured_summary=existing_doc.structured_summary,
                    evaluation_readiness=existing_doc.evaluation_readiness,
                )

    doc_id = uuid.uuid4()
    target_path = paths.UPLOAD_ROOT / f"{doc_id}.pdf"
    upload_marker: Path | None = None
    try:
        if runtime_db is not None:
            persistence._create_upload_intent(
                runtime_db,
                document_id=doc_id,
                title=title,
                course_title=course_title,
                lesson_title=lesson_title,
                program=canonical_program,
                source_type=source_type,
                policy_area=policy_area,
                file_path=str(target_path),
                uploaded_by=uploaded_by,
            )
            from .models import UserDocument

            runtime_db.add(UserDocument(user_id=uploaded_by, document_id=doc_id))
            runtime_db.flush()
        else:
            upload_marker = _create_upload_marker(doc_id, target_path)

        with target_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        response = _process_uploaded_document(
            doc_id=doc_id,
            target_path=target_path,
            source_type=source_type,
            title=title,
            course_title=course_title,
            lesson_title=lesson_title,
            program=canonical_program,
            policy_area=policy_area,
            uploaded_by=uploaded_by,
            original_filename=file.filename,
            runtime_db=runtime_db,
        )
        if (
            upload_marker is not None
            and response.processing_status != "CLEANUP_PENDING"
        ):
            _remove_upload_marker(upload_marker)
        return response
    except Exception:
        if runtime_db is not None:
            runtime_db.rollback()
        cleanup_ok = _cleanup_failed_upload(target_path)
        if runtime_db is not None:
            persistence._mark_interrupted_upload(runtime_db, doc_id, cleanup_ok)
        if upload_marker is not None and cleanup_ok:
            _remove_upload_marker(upload_marker)
        raise
    finally:
        if runtime_session is not None:
            runtime_session.close()


def _validate_upload(
    file: UploadFile,
    source_type: str,
    program: str | None,
    user_role: str = "faculty",
    policy_area: str | None = None,
) -> str | None:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise UnsupportedFileTypeError("Only PDF uploads are supported")
    if source_type not in SOURCE_TYPES:
        raise UnsupportedFileTypeError(f"Unsupported source_type: {source_type}")
    canonical_program = canonicalize_supported_program(program)
    # RBAC: only admins can upload institutional knowledge base documents.
    if user_role != "admin" and source_type in _ADMIN_ONLY_SOURCE_TYPES:
        raise ForbiddenUploadError(
            f"Only administrators can upload {source_type} documents. "
            "Faculty members can only upload SLM documents."
        )

    # Curriculum upload requires explicit canonical BSCS or BSInfoTech
    if source_type == "curriculum":
        if not program or not program.strip():
            raise UnsupportedFileTypeError(
                "Curriculum upload requires explicit canonical program "
                "'BSCS' or 'BSInfoTech'."
            )
        if program.strip() not in ("BSCS", "BSInfoTech"):
            if program.strip().upper() == "BSIT":
                raise UnsupportedFileTypeError(
                    "BSIT is a legacy read alias and cannot be used for uploads. "
                    "Use BSInfoTech."
                )
            raise UnsupportedFileTypeError(
                "Curriculum upload requires explicit canonical program "
                "'BSCS' or 'BSInfoTech'."
            )

    if source_type in ("rubric_sme", "rubric_coord", "rubric_gad", "rubric_itso"):
        raise UnsupportedFileTypeError(
            f"Direct PDF upload for {source_type} is not supported. "
            "Use structured rubric tables."
        )
    # Policy documents require a valid policy_area
    if source_type == "policy":
        if not (policy_area and policy_area.strip()):
            raise UnsupportedFileTypeError(
                "policy_area is required for policy documents."
            )
        if policy_area not in VALID_POLICY_AREAS:
            raise UnsupportedFileTypeError(
                f"Invalid policy_area '{policy_area}'. Valid values: "
                f"{', '.join(sorted(VALID_POLICY_AREAS))}."
            )
    # Non-policy documents must not have a policy_area
    if source_type != "policy" and policy_area:
        raise UnsupportedFileTypeError(
            "policy_area is only valid for policy documents."
        )
    if program and program.strip() and canonical_program is None:
        raise UnsupportedFileTypeError(
            "Unsupported program. Only BSCS and BSInfoTech are supported; "
            "BSIT is accepted as an alias."
        )
    return canonical_program


__all__ = ["create_document"]
