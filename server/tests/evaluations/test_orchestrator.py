"""Orchestrator tests for run_evaluation_job, Layer 3 honesty, and failure paths."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import run_evaluation_job
from server.modules.synthesis.models import MonitoringMatrix
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .conftest import _add_document, _seed_active_prompts


def test_orchestrator_layer3_honesty(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    from server.db.metadata import import_model_modules

    import_model_modules()
    from server.core.database import Base

    Base.metadata.create_all(engine)

    session = SessionLocal()
    owner = create_user(
        session,
        name="Owner",
        email="owner-orchestrator@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    session.commit()

    slm_id = _add_document(session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(session, owner_id=owner.user_id, source_type="syllabus")
    curriculum_id = _add_document(
        session, owner_id=owner.user_id, source_type="curriculum"
    )
    _seed_active_prompts(session)

    captured_context: dict[str, object] = {}

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_id,
        syllabus_id=syllabus_id,
        curriculum_id=curriculum_id,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    session.add(job)
    session.commit()

    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
    from server.modules.agents.supervisor import SupervisorResult
    monkeypatch.setattr(core_database, "get_session_factory", lambda: SessionLocal)

    seen_statuses: list[EvaluationStatus] = []
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from server.modules.evaluations.service import (
        transition_evaluation_status as real_transition,
    )

    def recording_transition(
        evaluation_id,
        new_status,
        db=None,
        *,
        error_message=None,
        execution_token=None,
        session=None,
    ):
        db = db or session
        if isinstance(new_status, str):
            new_status = EvaluationStatus(new_status)
        seen_statuses.append(new_status)
        return real_transition(
            evaluation_id,
            new_status,
            db,
            error_message=error_message,
            execution_token=execution_token,
        )

    monkeypatch.setattr(
        evaluation_orchestrator,
        "transition_evaluation_status",
        recording_transition,
    )

    def fake_run_evaluation(
        self, *, evaluation_id, document_id, chunks, query_text=None, context=None
    ):
        captured_context.update(context or {})
        assert context == {
            "reference_document_ids": {
                "syllabus": syllabus_id,
                "curriculum": curriculum_id,
            }
        }
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=[
                AgentEvaluationResult(
                    agent_name="sme",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=3,
                    criterion_scores=(
                        CriterionScore(
                            criterion_id="c1",
                            criterion_title="Criterion 1",
                            score=3,
                            justification="ok",
                        ),
                    ),
                    summary="ok",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    prompt_version_id=None,
                )
            ],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        fake_run_evaluation,
    )

    run_evaluation_job(job.evaluation_id)

    with SessionLocal() as readback:
        refreshed = readback.get(EvaluationJob, job.evaluation_id)
        assert refreshed is not None
        assert refreshed.status == EvaluationStatus.COMPLETED.value
        assert seen_statuses == [
            EvaluationStatus.PREPROCESSING,
            EvaluationStatus.EVALUATING,
            EvaluationStatus.SYNTHESIZING,
            EvaluationStatus.COMPLETED,
        ]
        assert refreshed.error_message is None
        assert readback.query(MonitoringMatrix).filter_by(document_id=slm_id).count() == 1
    assert captured_context == {
        "reference_document_ids": {
            "syllabus": syllabus_id,
            "curriculum": curriculum_id,
        }
    }


def test_orchestrator_partial_without_curriculum_completes(
    db_session, monkeypatch
) -> None:
    """A deliberate no-curriculum partial job skips Coordinator and ends COMPLETED."""
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
    from server.modules.agents.supervisor import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-partial-orch@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    _seed_active_prompts(db_session)

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_id,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
        partial_without_curriculum=True,
        partial_reason="No curriculum reference was available; Coordinator review was skipped.",
    )
    db_session.add(job)
    db_session.commit()

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    seen_statuses: list[EvaluationStatus] = []
    real_transition = evaluation_orchestrator.transition_evaluation_status

    def recording_transition(
        evaluation_id, new_status, db, *, error_message=None, execution_token=None
    ):
        seen_statuses.append(new_status)
        return real_transition(
            evaluation_id,
            new_status,
            db,
            error_message=error_message,
            execution_token=execution_token,
        )

    monkeypatch.setattr(
        evaluation_orchestrator,
        "transition_evaluation_status",
        recording_transition,
    )

    captured_agents: list[str] = []

    def fake_run_evaluation(
        self, *, evaluation_id, document_id, chunks, query_text=None, context=None
    ):
        nonlocal captured_agents
        captured_agents = [getattr(a, "agent_name", type(a).__name__) for a in self.agents]
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=[
                AgentEvaluationResult(
                    agent_name="sme",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=3,
                    criterion_scores=(
                        CriterionScore(
                            criterion_id="c1",
                            criterion_title="Criterion 1",
                            score=3,
                            justification="ok",
                        ),
                    ),
                    summary="ok",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    success=True,
                    prompt_version_id=None,
                ),
                AgentEvaluationResult(
                    agent_name="gad",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=3,
                    criterion_scores=(),
                    summary="ok",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    success=True,
                    prompt_version_id=None,
                ),
                AgentEvaluationResult(
                    agent_name="itso",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=3,
                    criterion_scores=(),
                    summary="ok",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    success=True,
                    prompt_version_id=None,
                ),
            ],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        fake_run_evaluation,
    )

    run_evaluation_job(job.evaluation_id)

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.COMPLETED.value
    assert "coordinator" not in captured_agents
    assert len(captured_agents) == 3
    assert refreshed.error_message is None
    assert seen_statuses == [
        EvaluationStatus.PREPROCESSING,
        EvaluationStatus.EVALUATING,
        EvaluationStatus.SYNTHESIZING,
        EvaluationStatus.COMPLETED,
    ]
    matrix_row = db_session.query(MonitoringMatrix).filter_by(
        document_id=slm_id
    ).first()
    assert matrix_row is not None
    assert matrix_row.evaluation_status == "COMPLETED_PARTIAL"


def test_orchestrator_completes_when_layer3_returns_outputs(
    db_session, monkeypatch
) -> None:
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
    from server.modules.agents.supervisor import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-layer3-empty@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )
    curriculum_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="curriculum"
    )
    _seed_active_prompts(db_session)

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_id,
        syllabus_id=syllabus_id,
        curriculum_id=curriculum_id,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(job)
    db_session.commit()

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    def fake_run_evaluation(
        self, *, evaluation_id, document_id, chunks, query_text=None, context=None
    ):
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=[
                AgentEvaluationResult(
                    agent_name="sme",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=4,
                    criterion_scores=(
                        CriterionScore(
                            criterion_id="c1",
                            criterion_title="Criterion 1",
                            score=4,
                            justification="great",
                        ),
                    ),
                    summary="great",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    success=True,
                    prompt_version_id=None,
                )
            ],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        fake_run_evaluation,
    )

    run_evaluation_job(job.evaluation_id)

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.COMPLETED.value
    assert refreshed.error_message is None


def test_orchestrator_accidental_agent_failure_ends_failed(
    db_session, monkeypatch
) -> None:
    """Accidental partial caused by agent failure in a full evaluation ends FAILED."""
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
    from server.modules.agents.supervisor import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-accidental-fail@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )
    curriculum_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="curriculum"
    )
    _seed_active_prompts(db_session)

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_id,
        syllabus_id=syllabus_id,
        curriculum_id=curriculum_id,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(job)
    db_session.commit()

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    def fake_run_evaluation_with_failure(
        self, *, evaluation_id, document_id, chunks, query_text=None, context=None
    ):
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=[
                AgentEvaluationResult(
                    agent_name="sme",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=3,
                    criterion_scores=(),
                    summary="ok",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    success=True,
                    prompt_version_id=None,
                ),
                AgentEvaluationResult(
                    agent_name="coordinator",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=0,
                    criterion_scores=(),
                    summary="",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=0,
                    success=False,
                    error_message="Coordinator LLM call failed",
                    prompt_version_id=None,
                ),
            ],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        fake_run_evaluation_with_failure,
    )

    # A failed Coordinator result triggers orchestrator._reconcile_coordinator_result's
    # independent-scoring fallback (see coordinator.py's module docstring) --
    # mock that fallback to also fail, so this stays a pure unit test (no real
    # LLM call) while preserving the scenario: Coordinator never recovers, so
    # the evaluation still ends FAILED.
    from server.modules.agents.coordinator import Coordinator

    def fake_run_full_independent_failure(self, **kwargs):
        raise RuntimeError("Coordinator LLM call failed")

    monkeypatch.setattr(
        Coordinator, "run_full_independent", fake_run_full_independent_failure
    )
    monkeypatch.setattr(
        evaluation_orchestrator, "get_llm_client_for_agent", lambda agent_name: None
    )

    run_evaluation_job(job.evaluation_id)

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.FAILED.value
    assert refreshed.error_message is not None
    assert "Coordinator" in refreshed.error_message
