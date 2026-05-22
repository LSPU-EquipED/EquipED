"""
BackgroundTask orchestrator for evaluations jobs.
"""

from __future__ import annotations

import uuid

from server.modules.agents.supervisor import Supervisor
from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.documents.models import Document
from server.modules.documents.service import get_document_chunks
from server.modules.evaluations.exceptions import EvaluationPipelineUnavailableError
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.service import transition_evaluation_status
from server.modules.synthesis.matrix import (
    compute_synthesized_score,
    upsert_monitoring_matrix,
)
from server.modules.synthesis.models import AgentResult, EvaluationFlag
from server.modules.synthesis.service import persist_agent_outputs


def run_evaluation_job(
    evaluation_id: uuid.UUID,
    db_session_factory=None,
) -> None:
    """Run the lifecycle through honest Phase 3 transitions."""

    if db_session_factory is None:
        from server.core.database import get_session_factory

        db_session_factory = get_session_factory()

    session = db_session_factory()
    try:
        job = session.get(EvaluationJob, evaluation_id)
        if job is None:
            raise EvaluationPipelineUnavailableError("Evaluation job not found.")

        document = session.get(Document, job.document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {job.document_id} not found")

        if job.syllabus_id is not None:
            syllabus = session.get(Document, job.syllabus_id)
            if syllabus is None:
                raise DocumentNotFoundError(f"Document {job.syllabus_id} not found")

        if job.curriculum_id is not None:
            curriculum = session.get(Document, job.curriculum_id)
            if curriculum is None:
                raise DocumentNotFoundError(f"Document {job.curriculum_id} not found")

        transition_evaluation_status(
            evaluation_id,
            EvaluationStatus.PREPROCESSING,
            session,
        )

        if not get_document_chunks(job.document_id, db=session):
            raise EvaluationPipelineUnavailableError(
                "Document has no chunks for evaluation."
            )

        transition_evaluation_status(
            evaluation_id,
            EvaluationStatus.EVALUATING,
            session,
        )
        slm_chunks = get_document_chunks(job.document_id, db=session)
        slm_text = "\n".join([chunk.text for chunk in slm_chunks if getattr(chunk, "text", None)])
        supervisor = Supervisor(db=session)
        supervisor_result = supervisor.run_evaluation(
            evaluation_id=evaluation_id,
            document_id=job.document_id,
            chunks=slm_chunks,
            query_text=slm_text,
            context={
                "reference_document_ids": {
                    **({"syllabus": job.syllabus_id} if job.syllabus_id else {}),
                    **({"curriculum": job.curriculum_id} if job.curriculum_id else {}),
                }
            },
        )
        if not supervisor_result.agent_results:
            raise EvaluationPipelineUnavailableError(
                "Layer 3 produced no usable agent outputs."
            )
        persist_agent_outputs(
            session,
            evaluation_id,
            job.document_id,
            supervisor_result.agent_results,
        )
        transition_evaluation_status(
            evaluation_id,
            EvaluationStatus.SYNTHESIZING,
            session,
        )

        agent_results = session.query(AgentResult).filter_by(
            evaluation_id=evaluation_id
        ).all()
        synthesis_result = compute_synthesized_score(agent_results)
        flag_count = session.query(EvaluationFlag).filter_by(
            evaluation_id=evaluation_id
        ).count()

        upsert_monitoring_matrix(
            db=session,
            document_id=job.document_id,
            evaluation_id=evaluation_id,
            evaluation_status=(
                "COMPLETED"
                if not synthesis_result["is_partial"]
                else "COMPLETED_PARTIAL"
            ),
            synthesized_score=synthesis_result["synthesized_score"],
            domain_scores=synthesis_result["domain_scores"],
            flag_count=flag_count,
        )

        final_status = (
            EvaluationStatus.COMPLETED
            if not synthesis_result["is_partial"]
            else EvaluationStatus.FAILED
        )
        partial_error = None
        if synthesis_result["is_partial"]:
            failed_errors = [
                f"{r.agent_name}: {r.error_message}"
                for r in agent_results
                if not r.success and r.error_message
            ]
            if failed_errors:
                partial_error = "; ".join(failed_errors)
        transition_evaluation_status(
            evaluation_id, final_status, session, error_message=partial_error
        )
        session.commit()
    except Exception as exc:
        try:
            session.rollback()
            transition_evaluation_status(
                evaluation_id,
                EvaluationStatus.FAILED,
                session,
                error_message=str(exc),
            )
        except Exception:
            pass
        raise
    finally:
        session.close()
