"""
BackgroundTask orchestrator for evaluations job. Sequential (Phase 1).
Transitions job through all required states or marks as FAILED on error.
"""

from __future__ import annotations
import uuid
from server.modules.evaluations.models import EvaluationStatus
from server.modules.evaluations.service import transition_evaluation_status

def run_evaluation_job(
    evaluation_id: uuid.UUID,
    document_id: uuid.UUID,
    db_session_factory=None,  # Function to get DB session, inject from app
) -> None:
    """Background processing of SLM evaluation job.
    Drives full lifecycle: SUBMITTED → PREPROCESSING → EMBEDDING → EVALUATING → SYNTHESIZING → COMPLETED|FAILED.
    """
    session = None
    try:
        if db_session_factory is None:
            raise RuntimeError("No DB session factory provided to orchestrator.")
        session_or_factory = db_session_factory()
        if hasattr(session_or_factory, "get") and hasattr(session_or_factory, "close"):
            session = session_or_factory
        elif callable(session_or_factory):
            session = session_or_factory()
        else:
            raise RuntimeError("DB session factory did not return a valid session.")
        # PREPROCESSING
        transition_evaluation_status(
            evaluation_id, EvaluationStatus.PREPROCESSING, session
        )
        # (stub) Validate/prepare source doc - would happen here

        # EMBEDDING
        transition_evaluation_status(
            evaluation_id, EvaluationStatus.EMBEDDING, session
        )
        # (stub) Ensure embeddings for doc - would happen here

        # EVALUATING
        transition_evaluation_status(
            evaluation_id, EvaluationStatus.EVALUATING, session
        )
        # (stub) Run agent/supervisor - would happen here

        # SYNTHESIZING
        transition_evaluation_status(
            evaluation_id, EvaluationStatus.SYNTHESIZING, session
        )
        # (stub) Do report synthesis - would happen here

        # COMPLETED
        transition_evaluation_status(
            evaluation_id, EvaluationStatus.COMPLETED, session
        )

    except Exception as exc:
        if session is not None:
            transition_evaluation_status(
                evaluation_id, EvaluationStatus.FAILED, session, error_message=str(exc)
            )
    finally:
        if session is not None:
            session.close()
