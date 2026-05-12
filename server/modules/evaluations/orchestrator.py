"""
BackgroundTask orchestrator for evaluations jobs.
"""

from __future__ import annotations

import uuid

from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.documents.models import Document
from server.modules.documents.service import get_document_chunks
from server.modules.evaluations.exceptions import EvaluationPipelineUnavailableError
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.service import transition_evaluation_status


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

        transition_evaluation_status(evaluation_id, EvaluationStatus.PREPROCESSING, session)

        if not get_document_chunks(job.document_id, db=session):
            raise EvaluationPipelineUnavailableError(
                "Document has no chunks for evaluation."
            )

        transition_evaluation_status(evaluation_id, EvaluationStatus.EMBEDDING, session)
        transition_evaluation_status(evaluation_id, EvaluationStatus.EVALUATING, session)
        raise EvaluationPipelineUnavailableError(
            "Layer 3 evaluation agents are not implemented yet."
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
