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
from server.modules.synthesis.models import AgentResult
from server.modules.synthesis.schemas import score_to_adjectival
from sqlalchemy import func, or_, select

logger = logging.getLogger(__name__)


def get_specialist_desk_queue(
    db: Any,
    target_agent: str,
    current_user: Any,
    program: str | None = None,
    document_id: uuid.UUID | None = None,
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
    if document_id is not None:
        doc_query = doc_query.filter(Document.document_id == document_id)
    total = doc_query.count()
    docs = (
        doc_query.order_by(Document.uploaded_at.desc(), Document.document_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    if not docs:
        return DeskQueueListResponse(items=[], total=total)

    doc_ids = [d.document_id for d in docs]

    # Deterministic ordering by submitted_at DESC, evaluation_id DESC
    jobs = (
        db.query(EvaluationJob)
        .filter(
            EvaluationJob.document_id.in_(doc_ids),
            EvaluationJob.submitted_by == current_user_id,
        )
        .order_by(
            EvaluationJob.submitted_at.desc(),
            EvaluationJob.evaluation_id.desc(),
        )
        .all()
    )

    # Group jobs for current user by doc_id and target_agent
    # The first one encountered is the latest due to the ORDER BY
    latest_user_jobs_by_doc_and_agent: dict[tuple[uuid.UUID, str], EvaluationJob] = {}
    all_user_eval_ids: list[uuid.UUID] = []
    for j in jobs:
        key = (j.document_id, j.target_agent)
        if key not in latest_user_jobs_by_doc_and_agent:
            latest_user_jobs_by_doc_and_agent[key] = j
            all_user_eval_ids.append(j.evaluation_id)

    # Fetch exact AgentResults for the authenticated user's latest jobs
    agent_results = (
        db.query(AgentResult)
        .filter(AgentResult.evaluation_id.in_(all_user_eval_ids))
        .all()
        if all_user_eval_ids
        else []
    )
    # Map (evaluation_id, agent_name) -> AgentResult
    agent_result_by_eval_and_agent = {
        (ar.evaluation_id, ar.agent_name): ar for ar in agent_results
    }

    items: list[DeskQueueItem] = []
    for doc in docs:
        user_job = latest_user_jobs_by_doc_and_agent.get(
            (doc.document_id, target_agent)
        )

        # Peer desks completed by the authenticated user's own latest jobs
        peer_completed_desks: list[str] = []
        for agent_code in ("sme", "coordinator", "gad", "itso"):
            if agent_code == target_agent:
                continue
            peer_job = latest_user_jobs_by_doc_and_agent.get(
                (doc.document_id, agent_code)
            )
            if peer_job is not None and str(peer_job.status).upper() == "COMPLETED":
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
                ar = agent_result_by_eval_and_agent.get(
                    (user_job.evaluation_id, target_agent)
                )
                if ar is not None and ar.subtotal is not None:
                    my_score = round(float(ar.subtotal), 2)
                    my_adjectival = score_to_adjectival(my_score)
            else:
                my_status = j_status
        else:
            my_status = "READY"

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
