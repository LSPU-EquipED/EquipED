"""Persist agent outputs for evaluation reporting."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.documents.models import DocumentChunk
from server.modules.synthesis.models import AgentResult, CriterionScore, EvaluationFlag
from server.modules.synthesis.schemas import SyllabusAlignmentStartResponse

logger = logging.getLogger(__name__)


def start_sme_syllabus_alignment(
    db: Any,
    evaluation_id: uuid.UUID,
    submitted_by: uuid.UUID,
    background_tasks: Any,
):
    """Validate and queue an alignment run independent of evaluation scoring."""
    from fastapi import HTTPException
    from server.modules.evaluations.models import EvaluationJob

    job = db.get(EvaluationJob, evaluation_id)
    if job is None or job.submitted_by != submitted_by:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    if job.syllabus_id is None:
        raise HTTPException(
            status_code=422, detail="A syllabus must be selected before alignment."
        )
    sme_result = (
        db.query(AgentResult)
        .filter_by(evaluation_id=evaluation_id, agent_name="sme")
        .one_or_none()
    )
    if sme_result is None or not sme_result.success:
        raise HTTPException(
            status_code=409,
            detail="SME scoring must complete successfully before alignment.",
        )

    current = (sme_result.advisory_outputs or {}).get("syllabus_alignment") or {}
    if current.get("processing_state") != "RUNNING":
        pending = {
            "status": "UNAVAILABLE",
            "statement": "Content-syllabus alignment is processing.",
            "syllabus_document_id": str(job.syllabus_id),
            "total_topics": 0,
            "aligned_topics": 0,
            "outcome_matches": [],
            "unmatched_topics": [],
            "advisory_only": True,
            "processing_state": "RUNNING",
        }
        sme_result.advisory_outputs = {
            **(sme_result.advisory_outputs or {}),
            "syllabus_alignment": pending,
        }
        db.commit()
        background_tasks.add_task(
            run_sme_syllabus_alignment_job,
            evaluation_id,
            sme_result.agent_result_id,
        )
    return SyllabusAlignmentStartResponse(
        evaluation_id=evaluation_id, processing_state="RUNNING"
    )


def run_sme_syllabus_alignment_job(
    evaluation_id: uuid.UUID, agent_result_id: uuid.UUID
) -> None:
    """Background worker that updates only SME advisory output JSON."""
    from server.core.database import get_session_factory
    from server.core.llm import get_llm_client_for_agent
    from server.modules.agents import syllabus_alignment
    from server.modules.documents.models import DocumentChunk
    from server.modules.evaluations.models import EvaluationJob

    session = get_session_factory()()
    try:
        job = session.get(EvaluationJob, evaluation_id)
        result_row = session.get(AgentResult, agent_result_id)
        if job is None or result_row is None or job.syllabus_id is None:
            return
        chunks = (
            session.query(DocumentChunk)
            .filter_by(document_id=job.document_id)
            .order_by(DocumentChunk.page_number, DocumentChunk.chunk_index)
            .all()
        )
        chunk_infos = [
            {
                "chunk_id": str(chunk.chunk_id),
                "page_number": chunk.page_number,
                "text": chunk.text,
            }
            for chunk in chunks
            if chunk.text
        ]
        try:
            alignment = syllabus_alignment.evaluate(
                get_llm_client_for_agent("sme"), chunk_infos, job.syllabus_id
            )
            alignment["processing_state"] = (
                "FAILED" if alignment["status"] == "UNAVAILABLE" else "COMPLETED"
            )
        except Exception as exc:
            logger.exception("Standalone SME syllabus alignment failed")
            alignment = syllabus_alignment.unavailable(
                "the advisory analysis failed", job.syllabus_id
            )
            alignment["processing_state"] = "FAILED"
            alignment["statement"] = f"{alignment['statement']} ({str(exc)[:200]})"
        result_row.advisory_outputs = {
            **(result_row.advisory_outputs or {}),
            "syllabus_alignment": alignment,
        }
        session.commit()
    finally:
        session.close()


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
                provenance=agent_result.provenance,
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
            provenance=agent_result.provenance,
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
    "run_sme_syllabus_alignment_job",
    "start_sme_syllabus_alignment",
]
