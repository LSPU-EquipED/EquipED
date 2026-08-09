"""Persist agent outputs and assemble evaluation reporting for the synthesis module."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.provenance import sanitize_provenance
from server.modules.documents.metadata import canonicalize_supported_program
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.exceptions import (
    EvaluationResultsNotFoundError,
    UnsupportedProgramFilterError,
)
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
from sqlalchemy import func

logger = logging.getLogger(__name__)


def persist_agent_outputs(
    db: Any,
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
    agent_results: list[AgentEvaluationResult],
) -> None:
    for agent_result in agent_results:
        if not agent_result.success:
            result_row = AgentResult(
                agent_result_id=uuid.uuid4(),
                evaluation_id=evaluation_id,
                document_id=document_id,
                agent_name=agent_result.agent_name,
                prompt_version_id=agent_result.prompt_version_id,
                subtotal=agent_result.subtotal,
                processing_seconds=agent_result.processing_seconds,
                token_count=agent_result.token_count,
                model_name=agent_result.model_name,
                summary=agent_result.summary,
                success=False,
                error_message=agent_result.error_message,
                raw_response=agent_result.raw_response,
                provenance=sanitize_provenance(agent_result.provenance),
                advisory_outputs=agent_result.advisory_outputs,
            )
            db.add(result_row)
            db.flush()
            continue

        result_row = AgentResult(
            agent_result_id=uuid.uuid4(),
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_name=agent_result.agent_name,
            prompt_version_id=agent_result.prompt_version_id,
            subtotal=agent_result.subtotal,
            processing_seconds=agent_result.processing_seconds,
            token_count=agent_result.token_count,
            model_name=agent_result.model_name,
            summary=agent_result.summary,
            success=agent_result.success,
            error_message=agent_result.error_message,
            raw_response=agent_result.raw_response,
            provenance=sanitize_provenance(agent_result.provenance),
            advisory_outputs=agent_result.advisory_outputs,
        )
        db.add(result_row)
        db.flush()

        for score in agent_result.criterion_scores:
            valid_chunk_ids = _validated_chunk_ids(db, score.chunk_ids)
            score_row = CriterionScore(
                agent_result_id=result_row.agent_result_id,
                evaluation_id=evaluation_id,
                document_id=document_id,
                criterion_id=score.criterion_id,
                criterion_title=score.criterion_title,
                score=score.score,
                justification=score.justification,
                evidence=(json.dumps(list(score.evidence)) if score.evidence else None),
                chunk_ids=(
                    json.dumps([str(chunk_id) for chunk_id in valid_chunk_ids])
                    if valid_chunk_ids
                    else None
                ),
            )
            db.add(score_row)
            db.flush()

            if score.score <= 2:
                for chunk_id in valid_chunk_ids:
                    flag_row = EvaluationFlag(
                        evaluation_id=evaluation_id,
                        document_id=document_id,
                        agent_result_id=result_row.agent_result_id,
                        criterion_score_id=score_row.criterion_score_id,
                        chunk_id=chunk_id,
                        criterion_id=score.criterion_id,
                        score=score.score,
                        reason=score.justification,
                    )
                    db.add(flag_row)

    db.commit()


def persist_evaluation_results(
    db: Any,
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
    agent_results: list[AgentEvaluationResult],
) -> None:
    """Compatibility wrapper for orchestrator callers."""

    persist_agent_outputs(db, evaluation_id, document_id, agent_results)


def get_evaluation_results(
    evaluation_id: uuid.UUID,
    current_user_id: uuid.UUID,
    db: Any,
) -> EvaluationResultsResponse:
    """Assemble the full evaluation results response for an owner.

    Ownership is enforced here: a missing job or a job not submitted by
    ``current_user_id`` raises ``EvaluationResultsNotFoundError`` so the
    router can mask non-ownership as a 404.
    """
    job = db.get(EvaluationJob, evaluation_id)
    if job is None or job.submitted_by != current_user_id:
        raise EvaluationResultsNotFoundError("Evaluation not found")

    document = db.get(Document, job.document_id)
    agent_results = db.query(AgentResult).filter_by(evaluation_id=evaluation_id).all()
    agent_name_map = {r.agent_result_id: r.agent_name for r in agent_results}
    criterion_scores = (
        db.query(CriterionScore).filter_by(evaluation_id=evaluation_id).all()
    )
    flags = db.query(EvaluationFlag).filter_by(evaluation_id=evaluation_id).all()

    synthesis_result = compute_synthesized_score(
        agent_results,
        force_partial=job.partial_without_curriculum,
        partial_reason=job.partial_reason,
    )

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
            "provenance": result.provenance,
            "summary": result.summary,
        }
        for result in agent_results
    }

    duration_seconds = None
    if job.completed_at and job.submitted_at:
        duration_seconds = (job.completed_at - job.submitted_at).total_seconds()

    return EvaluationResultsResponse(
        evaluation_id=job.evaluation_id,
        document_id=job.document_id,
        syllabus_id=job.syllabus_id,
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
                agent_id=agent_name_map.get(
                    flag.agent_result_id, str(flag.agent_result_id)
                ),
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
        partial_reason=synthesis_result.get("partial_reason") or job.partial_reason,
        evaluation_status=job.status,
        submitted_at=job.submitted_at,
        completed_at=job.completed_at,
        duration_seconds=duration_seconds,
    )


def get_monitoring_matrix(
    program: str | None,
    status: str | None,
    page: int,
    page_size: int,
    db: Any,
) -> MatrixListResponse:
    """Assemble the monitoring matrix list response with filtering and pagination.

    Raises ``UnsupportedProgramFilterError`` when the ``program`` filter is
    not a supported program (so the router can map it to a 422).
    """
    query = db.query(MonitoringMatrix)

    if program:
        canonical_program = canonicalize_supported_program(program)
        if canonical_program is None:
            raise UnsupportedProgramFilterError(
                "Unsupported program filter. Only BSCS and BSInfoTech are "
                "supported; BSIT is accepted as an alias."
            )
        values = [canonical_program]
        if canonical_program == "BSInfoTech":
            values.append("BSIT")
        query = query.filter(
            func.lower(MonitoringMatrix.program).in_(
                [value.lower() for value in values]
            )
        )
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


def _validated_chunk_ids(db: Any, chunk_ids: tuple[str, ...]) -> list[uuid.UUID]:
    valid_chunk_ids: list[uuid.UUID] = []
    for chunk_id in chunk_ids:
        try:
            parsed_chunk_id = uuid.UUID(str(chunk_id))
        except (TypeError, ValueError, AttributeError):
            continue
        if db.get(DocumentChunk, parsed_chunk_id) is None:
            continue
        if parsed_chunk_id not in valid_chunk_ids:
            valid_chunk_ids.append(parsed_chunk_id)
    return valid_chunk_ids


__all__ = [
    "persist_agent_outputs",
    "persist_evaluation_results",
    "get_evaluation_results",
    "get_monitoring_matrix",
]
