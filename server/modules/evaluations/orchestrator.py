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

        syllabus = session.get(Document, job.syllabus_id)
        if syllabus is None:
            raise DocumentNotFoundError(f"Document {job.syllabus_id} not found")

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
        supervisor = Supervisor(db=session)
        supervisor_result = supervisor.run_evaluation(
            evaluation_id=evaluation_id,
            document_id=job.document_id,
            chunks=get_document_chunks(job.document_id, db=session),
            context={
                "reference_document_ids": {
                    "syllabus": job.syllabus_id,
                    "curriculum": job.curriculum_id,
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
        raise EvaluationPipelineUnavailableError(
            "Layer 4 synthesis/completion is not implemented yet."
        )
    except Exception as exc:
        try:
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
