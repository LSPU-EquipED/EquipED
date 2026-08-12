"""Orchestrator tests for claimed execution, Layer 3 honesty, and failure paths."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import _execute_claimed_evaluation
from server.modules.evaluations.service import acquire_evaluation_execution
from server.modules.synthesis.models import MonitoringMatrix
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .conftest import _add_document, _seed_active_prompts


def _run_claimed(evaluation_id, session_factory):
    token = uuid4()
    with session_factory() as session:
        assert acquire_evaluation_execution(session, evaluation_id, token)
        session.commit()
    return _execute_claimed_evaluation(
        evaluation_id, execution_token=token, db_session_factory=session_factory
    )


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
    from server.modules.agents.supervision.result import SupervisorResult

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
        expected_status=None,
        commit=True,
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
            expected_status=expected_status,
            commit=commit,
        )

    monkeypatch.setattr(
        evaluation_orchestrator,
        "transition_evaluation_status",
        recording_transition,
    )

    def fake_run_evaluation(
        self,
        *,
        evaluation_id,
        document_id,
        chunks,
        query_text=None,
        context=None,
        heartbeat_callback=None,
    ):
        if callable(heartbeat_callback):
            heartbeat_callback()
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
                ),
                *[
                    AgentEvaluationResult(
                        agent_name=agent_name,
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
                    )
                    for agent_name in ("gad", "itso", "coordinator")
                ],
            ],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        fake_run_evaluation,
    )
    monkeypatch.setattr(
        evaluation_orchestrator,
        "_reconcile_coordinator_result",
        lambda results, **kwargs: results,
    )

    _run_claimed(job.evaluation_id, SessionLocal)

    with SessionLocal() as readback:
        refreshed = readback.get(EvaluationJob, job.evaluation_id)
        assert refreshed is not None
        assert refreshed.status == EvaluationStatus.COMPLETED.value
        assert seen_statuses == [
            EvaluationStatus.EVALUATING,
            EvaluationStatus.SYNTHESIZING,
            EvaluationStatus.COMPLETED,
        ]
        assert refreshed.error_message is None
        assert (
            readback.query(MonitoringMatrix).filter_by(document_id=slm_id).count() == 1
        )  # noqa: E501
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
    from server.modules.agents.supervision.result import SupervisorResult
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
        partial_reason="No curriculum reference was available; Coordinator review was skipped.",  # noqa: E501
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
        evaluation_id,
        new_status,
        db,
        *,
        error_message=None,
        execution_token=None,
        expected_status=None,
        commit=True,
    ):
        seen_statuses.append(new_status)
        return real_transition(
            evaluation_id,
            new_status,
            db,
            error_message=error_message,
            execution_token=execution_token,
            expected_status=expected_status,
            commit=commit,
        )

    monkeypatch.setattr(
        evaluation_orchestrator,
        "transition_evaluation_status",
        recording_transition,
    )

    captured_agents: list[str] = []

    def fake_run_evaluation(
        self,
        *,
        evaluation_id,
        document_id,
        chunks,
        query_text=None,
        context=None,
        heartbeat_callback=None,
    ):
        if callable(heartbeat_callback):
            heartbeat_callback()
        nonlocal captured_agents
        captured_agents = [
            getattr(a, "agent_name", type(a).__name__) for a in self.agents
        ]  # noqa: E501
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
    monkeypatch.setattr(
        evaluation_orchestrator,
        "_reconcile_coordinator_result",
        lambda results, **kwargs: results,
    )

    _run_claimed(job.evaluation_id, session_factory)

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.COMPLETED.value
    assert "coordinator" not in captured_agents
    assert len(captured_agents) == 3
    assert refreshed.error_message is None
    assert seen_statuses == [
        EvaluationStatus.EVALUATING,
        EvaluationStatus.SYNTHESIZING,
        EvaluationStatus.COMPLETED,
    ]
    matrix_row = (
        db_session.query(MonitoringMatrix).filter_by(document_id=slm_id).first()
    )
    assert matrix_row is not None
    assert matrix_row.evaluation_status == "COMPLETED_PARTIAL"


def test_orchestrator_model_validation_failure_is_nonfatal_and_secret_free(
    db_session, monkeypatch, caplog
) -> None:
    """Model-validation postprocessing failures do not fail a deliberate partial run."""
    import re

    from server.core import database as core_database
    from server.modules.admin import model_validation_service
    from server.modules.agents.contracts import AgentEvaluationResult
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-model-validation-failure@example.com",
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
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        partial_without_curriculum=True,
        partial_reason="Deliberate partial evaluation",
    )
    db_session.add(job)
    db_session.commit()

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    def fake_run_evaluation(
        self,
        *,
        evaluation_id,
        document_id,
        chunks,
        query_text=None,
        context=None,
        heartbeat_callback=None,
    ):
        if callable(heartbeat_callback):
            heartbeat_callback()
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
                *[
                    AgentEvaluationResult(
                        agent_name=agent_name,
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
                    )
                    for agent_name in ("gad", "itso")
                ],
            ],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor, "run_evaluation", fake_run_evaluation
    )
    monkeypatch.setattr(
        model_validation_service,
        "sync_model_validation_criterion_results",
        lambda *args: (_ for _ in ()).throw(
            RuntimeError("MODEL_VALIDATION_SECRET_TEXT")
        ),
    )
    monkeypatch.setattr(
        model_validation_service, "assess_model_validation_toxicity", lambda *args: None
    )

    with caplog.at_level("WARNING"):
        _run_claimed(job.evaluation_id, session_factory)

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.COMPLETED.value
    assert "MODEL_VALIDATION_SECRET_TEXT" not in caplog.text
    assert re.search(
        r"category=RuntimeError reference=[0-9a-f]{16}(?:\s|$)", caplog.text
    )


def test_orchestrator_loads_slm_chunks_once(monkeypatch, db_session) -> None:
    """get_document_chunks is queried once, before the empty check, and reused.

    The same immutable ``slm_chunks`` list must feed both the emptiness guard
    and the supervisor/synthesis path — no duplicate back-to-back query.
    """
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-chunk-once@example.com",
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
        partial_reason="focused chunk-reuse test",
    )
    db_session.add(job)
    db_session.commit()

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    real_get_chunks = evaluation_orchestrator.get_document_chunks
    calls: list[object] = []

    def counting_get_chunks(document_id, db=None):
        calls.append(document_id)
        return real_get_chunks(document_id, db=db)

    monkeypatch.setattr(
        evaluation_orchestrator, "get_document_chunks", counting_get_chunks
    )

    def fake_run_evaluation(
        self,
        *,
        evaluation_id,
        document_id,
        chunks,
        query_text=None,
        context=None,
        heartbeat_callback=None,
    ):
        if callable(heartbeat_callback):
            heartbeat_callback()
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
                *[
                    AgentEvaluationResult(
                        agent_name=agent_name,
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
                    )
                    for agent_name in ("gad", "itso")
                ],
            ],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor, "run_evaluation", fake_run_evaluation
    )

    _run_claimed(job.evaluation_id, session_factory)

    assert calls == [slm_id]  # exactly one chunk load
    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.COMPLETED.value


def test_orchestrator_completes_when_layer3_returns_outputs(
    db_session, monkeypatch
) -> None:
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
    from server.modules.agents.sme import registry
    from server.modules.agents.supervision.result import SupervisorResult
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
        self,
        *,
        evaluation_id,
        document_id,
        chunks,
        query_text=None,
        context=None,
        heartbeat_callback=None,
    ):
        if callable(heartbeat_callback):
            heartbeat_callback()
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=[
                AgentEvaluationResult(
                    agent_name="sme",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=30,
                    criterion_scores=tuple(
                        CriterionScore(
                            criterion_id=criterion_code,
                            criterion_title=f"{criterion_code} title",
                            score=3,
                            justification="great",
                        )
                        for criterion_code in sorted(registry.REGISTERED_CODES)
                    ),
                    summary="great",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    success=True,
                    prompt_version_id=None,
                ),
                *[
                    AgentEvaluationResult(
                        agent_name=agent_name,
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
                    )
                    for agent_name in ("gad", "itso")
                ],
                AgentEvaluationResult(
                    agent_name="coordinator",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=4,
                    criterion_scores=(
                        CriterionScore(
                            criterion_id="A-05",
                            criterion_title="A-05 title",
                            score=4,
                            justification="curriculum evidence",
                            evidence=("quote",),
                        ),
                    ),
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

    _run_claimed(job.evaluation_id, session_factory)

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.COMPLETED.value
    assert refreshed.error_message is None


def test_orchestrator_accidental_agent_failure_ends_failed(
    db_session, monkeypatch, caplog
) -> None:
    """Accidental partial caused by agent failure in a full evaluation ends FAILED."""
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult
    from server.modules.agents.supervision.result import SupervisorResult
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
        self,
        *,
        evaluation_id,
        document_id,
        chunks,
        query_text=None,
        context=None,
        heartbeat_callback=None,
    ):
        if callable(heartbeat_callback):
            heartbeat_callback()
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
                *[
                    AgentEvaluationResult(
                        agent_name=agent_name,
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
                    )
                    for agent_name in ("gad", "itso")
                ],
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

    _run_claimed(job.evaluation_id, session_factory)

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.FAILED.value
    assert refreshed.error_message is not None
    assert "coordinator" in refreshed.error_message.lower()
    assert "provider-secret" not in refreshed.error_message
    assert "provider-secret" not in caplog.text
