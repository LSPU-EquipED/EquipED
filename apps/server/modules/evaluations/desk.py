"""Specialist desk queue aggregation and domain filtering."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from server.modules.auth.models import UserRole
from server.modules.documents.metadata import canonicalize_supported_program
from server.modules.documents.models import Document, UserDocument
from server.modules.evaluations.agent_schedule import VALID_TARGET_AGENTS
from server.modules.evaluations.exceptions import (
    ForbiddenEvaluationAccessError,
    InvalidEvaluationTargetError,
)
from server.modules.evaluations.models import EvaluationJob
from server.modules.evaluations.schemas import (
    DeskQueueItem,
    DeskQueueListResponse,
)
from server.modules.synthesis.models import MonitoringMatrix
from server.modules.synthesis.schemas import score_to_adjectival
from sqlalchemy import func, or_, select

logger = logging.getLogger(__name__)


def get_specialist_desk_queue(
    db: Any,
    target_agent: str,
    current_user: Any,
    program: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> DeskQueueListResponse:
    """Fetch document queue for specialist desk with status and peer convergence."""
    if target_agent not in VALID_TARGET_AGENTS:
        raise InvalidEvaluationTargetError(f"Invalid target_agent '{target_agent}'.")

    user_role = getattr(current_user, "role", None)
    is_admin = user_role == UserRole.ADMIN or str(user_role) == "admin"
    perms = getattr(current_user, "evaluator_permissions", None) or ()
    if not is_admin and perms and target_agent not in perms:
        raise ForbiddenEvaluationAccessError(
            f"User does not have evaluator permission for '{target_agent}'."
        )
    if db is None:
        return DeskQueueListResponse(items=[], total=0)

    current_user_id = getattr(current_user, "id", None) or getattr(
        current_user, "user_id", None
    )

    doc_query = db.query(Document).filter(
        func.lower(Document.source_type) == "slm",
        func.upper(Document.processing_status) == "PROCESSED",
    )

    if not is_admin:
        user_storage_doc_ids = select(UserDocument.document_id).where(
            UserDocument.user_id == current_user_id
        )
        user_job_docs = select(EvaluationJob.document_id).where(
            EvaluationJob.submitted_by == current_user_id
        )
        doc_query = doc_query.filter(
            or_(
                Document.document_id.in_(user_storage_doc_ids),
                Document.uploaded_by == current_user_id,
                Document.document_id.in_(user_job_docs),
            )
        )
    if program:
        canonical_program = canonicalize_supported_program(program)
        if canonical_program is None:
            raise InvalidEvaluationTargetError(
                "Unsupported program filter. Only BSCS and BSInfoTech are supported; "
                "BSIT is accepted as an alias."
            )
        values = [canonical_program]
        if canonical_program == "BSInfoTech":
            values.append("BSIT")
        doc_query = doc_query.filter(
            func.lower(Document.program).in_([v.lower() for v in values])
        )
    total = doc_query.count()
    docs = (
        doc_query.order_by(Document.uploaded_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    if not docs:
        return DeskQueueListResponse(items=[], total=total)

    doc_ids = [d.document_id for d in docs]

    matrices = (
        db.query(MonitoringMatrix)
        .filter(MonitoringMatrix.document_id.in_(doc_ids))
        .all()
    )
    matrix_by_doc = {m.document_id: m for m in matrices}

    jobs = (
        db.query(EvaluationJob)
        .filter(
            EvaluationJob.document_id.in_(doc_ids),
            EvaluationJob.target_agent == target_agent,
        )
        .order_by(EvaluationJob.submitted_at.desc())
        .all()
    )

    current_user_id = getattr(current_user, "id", None) or getattr(
        current_user, "user_id", None
    )

    jobs_by_doc: dict[uuid.UUID, list[EvaluationJob]] = {}
    for j in jobs:
        jobs_by_doc.setdefault(j.document_id, []).append(j)

    items: list[DeskQueueItem] = []
    for doc in docs:
        matrix = matrix_by_doc.get(doc.document_id)
        doc_jobs = jobs_by_doc.get(doc.document_id, [])

        # Prioritize job submitted by current user, else fallback to latest job
        user_job = None
        for j in doc_jobs:
            if current_user_id and j.submitted_by == current_user_id:
                user_job = j
                break
        if user_job is None and doc_jobs:
            user_job = doc_jobs[0]

        peer_completed_desks: list[str] = []
        if is_admin and matrix and isinstance(matrix.domain_scores_json, dict):
            for agent_code in ("sme", "coordinator", "gad", "itso"):
                if agent_code in matrix.domain_scores_json:
                    agent_val = matrix.domain_scores_json[agent_code]
                    st = (
                        agent_val.get("status", "OK")
                        if isinstance(agent_val, dict)
                        else "OK"
                    )
                    if st not in ("ERROR", "FAILED"):
                        peer_completed_desks.append(agent_code)
        peer_completed_count = len(peer_completed_desks)
        my_score: float | None = None
        my_adjectival: str | None = None

        if user_job is not None:
            j_status = str(user_job.status).upper()
            if j_status in ("SUBMITTED", "PREPROCESSING", "EVALUATING", "SYNTHESIZING"):
                my_status = "EVALUATING"
            elif j_status == "FAILED":
                my_status = "FAILED"
            elif j_status == "COMPLETED":
                my_status = "COMPLETED"
            else:
                my_status = j_status
        else:
            if (
                matrix
                and isinstance(matrix.domain_scores_json, dict)
                and target_agent in matrix.domain_scores_json
            ):
                my_status = "COMPLETED"
            else:
                my_status = "READY"

        if my_status == "COMPLETED":
            if (
                matrix
                and isinstance(matrix.domain_scores_json, dict)
                and target_agent in matrix.domain_scores_json
            ):
                domain_val = matrix.domain_scores_json[target_agent]
                if isinstance(domain_val, dict):
                    sub = domain_val.get("subtotal")
                    if sub is not None:
                        my_score = round(float(sub), 2)
                        my_adjectival = domain_val.get(
                            "adjectival_rating"
                        ) or score_to_adjectival(my_score)

        items.append(
            DeskQueueItem(
                document_id=doc.document_id,
                title=doc.title,
                course_code=doc.course_code,
                program=doc.program,
                uploaded_at=doc.uploaded_at,
                my_status=my_status,
                my_score=my_score,
                my_adjectival=my_adjectival,
                peer_completed_count=peer_completed_count,
                peer_completed_desks=peer_completed_desks,
            )
        )

    return DeskQueueListResponse(items=items, total=total)


__all__ = ["get_specialist_desk_queue"]
