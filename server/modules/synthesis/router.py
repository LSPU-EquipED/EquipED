"""Routers for synthesis results and monitoring matrix views."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from server.core.database import get_db_session
from server.modules.auth.dependencies import require_admin, require_authenticated_user
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.matrix import compute_synthesized_score
from server.modules.synthesis.models import (
    AgentResult,
    CriterionScore,
    EvaluationFlag,
    MonitoringMatrix,
)
from server.modules.synthesis.schemas import (
    EvaluationFlagItem,
    EvaluationResultsResponse,
    MatrixListResponse,
    MatrixRowItem,
)

router = APIRouter(prefix="/evaluations", tags=["synthesis"])
@router.get("/{evaluation_id}/results", response_model=EvaluationResultsResponse)
def get_evaluation_results(
    evaluation_id: uuid.UUID,
    current_user=Depends(require_authenticated_user),
    db=Depends(get_db_session),
):
    job = db.get(EvaluationJob, evaluation_id)
    if job is None or job.submitted_by != current_user.id:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    document = db.get(Document, job.document_id)
    agent_results = db.query(AgentResult).filter_by(evaluation_id=evaluation_id).all()
    agent_name_map = {r.agent_result_id: r.agent_name for r in agent_results}
    criterion_scores = db.query(CriterionScore).filter_by(evaluation_id=evaluation_id).all()
    flags = db.query(EvaluationFlag).filter_by(evaluation_id=evaluation_id).all()

    synthesis_result = compute_synthesized_score(agent_results)

    criteria_by_result: dict[uuid.UUID, list[CriterionScore]] = {}
    for score in criterion_scores:
        criteria_by_result.setdefault(score.agent_result_id, []).append(score)

    # Build a lookup from criterion_score_id -> CriterionScore for flag resolution
    criterion_by_id: dict[uuid.UUID, CriterionScore] = {
        score.criterion_score_id: score for score in criterion_scores
    }

    domain_scores = {
        result.agent_name: {
            "criteria": [
                {
                    "criterion_id": score.criterion_id,
                    "criterion_text": score.criterion_title,
                    "score": score.score,
                    "justification": score.justification,
                    "evidence": score.evidence,
                    "chunk_ids": score.chunk_ids,
                }
                for score in criteria_by_result.get(result.agent_result_id, [])
            ],
            "subtotal": float(result.subtotal),
            "max_score": 4,
            "status": "OK" if result.success else "ERROR",
            "adjectival_rating": synthesis_result["domain_scores"]
                .get(result.agent_name, {})
                .get("adjectival_rating"),
        }
        for result in agent_results
    }

    return EvaluationResultsResponse(
        evaluation_id=job.evaluation_id,
        document_id=job.document_id,
        document_title=document.title if document else None,
        program=document.program if document else None,
        synthesized_score=float(synthesis_result["synthesized_score"]),
        overall_score=synthesis_result.get("overall_score"),
        adjectival_rating=synthesis_result.get("adjectival_rating"),
        domain_scores=domain_scores,
        flags=[
            EvaluationFlagItem(
                flag_id=flag.evaluation_flag_id,
                evaluation_id=flag.evaluation_id,
                agent_id=agent_name_map.get(flag.agent_result_id, str(flag.agent_result_id)),
                criterion_id=flag.criterion_id,
                criterion_text=criterion_by_id[flag.criterion_score_id].criterion_title
                if flag.criterion_score_id in criterion_by_id
                else flag.criterion_id,
                score=flag.score,
                justification=flag.reason,
                chunk_id=flag.chunk_id,
            )
            for flag in flags
        ],
        active_agents=list(synthesis_result["active_agents"]),
        failed_agents=list(synthesis_result["failed_agents"]),
        is_partial=bool(synthesis_result["is_partial"]),
        evaluation_status=job.status,
        completed_at=job.completed_at,
    )


@router.get("/matrix", response_model=MatrixListResponse)
def get_monitoring_matrix(
    program: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_admin),
    db=Depends(get_db_session),
):
    query = db.query(MonitoringMatrix)

    if program:
        query = query.filter(MonitoringMatrix.program == program)
    if status:
        query = query.filter(MonitoringMatrix.evaluation_status == status)

    total = query.count()
    rows = (
        query.order_by(MonitoringMatrix.last_updated.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    doc_ids = [row.document_id for row in rows]
    docs = {
        d.document_id: d
        for d in db.query(Document).filter(Document.document_id.in_(doc_ids)).all()
    }

    items = []
    for row in rows:
        doc = docs.get(row.document_id)
        items.append(
            MatrixRowItem(
                matrix_id=row.matrix_id,
                document_id=row.document_id,
                evaluation_id=row.evaluation_id,
                faculty_name=row.faculty_name,
                program=row.program,
                document_title=doc.title if doc else None,
                evaluation_status=row.evaluation_status,
                synthesized_score=float(row.synthesized_score)
                if row.synthesized_score is not None
                else None,
                domain_scores=row.domain_scores_json,
                flag_count=row.flag_count,
                feedback_status=row.feedback_status,
                last_updated=row.last_updated,
            )
        )

    return MatrixListResponse(items=items, total=total, page=page, page_size=page_size)


__all__ = ["router"]
