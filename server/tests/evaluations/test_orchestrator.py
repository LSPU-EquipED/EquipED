"""Orchestrator tests for claimed execution, Layer 3 honesty, and failure paths."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.exceptions import EvaluationPipelineFailure
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import _execute_claimed_evaluation
from server.modules.evaluations.service import acquire_evaluation_execution
from server.modules.synthesis.models import (
    AgentResult,
    MonitoringMatrix,
)
from server.modules.synthesis.models import (
    CriterionScore as StoredCriterionScore,
)
from server.tests.evaluations.snapshot_test_helpers import (
    make_agent_result,
    make_scheduled_agent_results,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .conftest import _add_document, _seed_active_prompts, _seed_all_rubrics


def _run_claimed(evaluation_id, session_factory):
    token = uuid4()
    with session_factory() as session:
        assert acquire_evaluation_execution(session, evaluation_id, token)
        session.commit()
    try:
        return _execute_claimed_evaluation(
            evaluation_id, execution_token=token, db_session_factory=session_factory
        )
    except EvaluationPipelineFailure:
        return None


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
    admin = create_user(
        session,
        name="Admin",
        email="admin-orchestrator@lspu.edu.ph",
        password="password123",
        role=UserRole.ADMIN,
    )
    owner = create_user(
        session,
        name="Owner",
        email="owner-orchestrator@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    session.commit()

    slm_id = _add_document(session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(session, owner_id=owner.user_id, source_type="syllabus")
    curriculum_id = _add_document(
        session, owner_id=admin.user_id, source_type="curriculum"
    )
    _seed_active_prompts(session)
    _seed_all_rubrics(session)

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
        confirmed_program="BSCS",
    )
    session.add(job)
    session.commit()

    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda *args, **kwargs: True,
    )

    from server.core import database as core_database
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

    captured_snapshots: tuple | None = None

    def fake_run_evaluation(
        self,
        *,
        evaluation_id,
        document_id,
        chunks,
        form_snapshots,
        query_text=None,
        context=None,
        heartbeat_callback=None,
    ):
        nonlocal captured_snapshots
        captured_snapshots = form_snapshots
        if callable(heartbeat_callback):
            heartbeat_callback()
        captured_context.update(context or {})
        assert context == {
            "reference_document_ids": {
                "syllabus": syllabus_id,
                "curriculum": curriculum_id,
            },
            "confirmed_program": "BSCS",
        }
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=make_scheduled_agent_results(
                evaluation_id,
                document_id,
                partial_without_curriculum=False,
            ),
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        fake_run_evaluation,
    )

    _run_claimed(job.evaluation_id, SessionLocal)

    with SessionLocal() as readback:
        refreshed = readback.get(EvaluationJob, job.evaluation_id)
        assert refreshed is not None
        assert refreshed.status == EvaluationStatus.COMPLETED.value
        assert isinstance(captured_snapshots, tuple)
        assert [s.agent_id for s in captured_snapshots] == [
            "sme",
            "coordinator",
            "gad",
            "itso",
        ]
        assert all(s.evaluation_id == job.evaluation_id for s in captured_snapshots)
        assert seen_statuses == [
            EvaluationStatus.EVALUATING,
            EvaluationStatus.SYNTHESIZING,
            EvaluationStatus.COMPLETED,
        ]
        assert refreshed.error_message is None
        assert (
            readback.query(MonitoringMatrix).filter_by(document_id=slm_id).count() == 1
        )  # noqa: E501
        coord_result = (
            readback.query(AgentResult)
            .filter_by(evaluation_id=job.evaluation_id, agent_name="coordinator")
            .one()
        )
        coord_scores = (
            readback.query(StoredCriterionScore)
            .filter_by(agent_result_id=coord_result.agent_result_id)
            .all()
        )
        assert len(coord_scores) == 10
        assert {s.criterion_id for s in coord_scores} == {
            "OP-01",
            "OP-02",
            "OP-03",
            "OP-04",
            "OP-05",
            "A-01",
            "A-02",
            "A-03",
            "A-04",
            "A-05",
        }
    assert captured_context == {
        "reference_document_ids": {
            "syllabus": syllabus_id,
            "curriculum": curriculum_id,
        },
        "confirmed_program": "BSCS",
    }


def test_orchestrator_partial_without_curriculum_completes(
    db_session, monkeypatch
) -> None:
    """A deliberate no-curriculum partial job skips Coordinator and ends COMPLETED."""
    from server.core import database as core_database
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-partial-orch@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    _seed_active_prompts(db_session)
    _seed_all_rubrics(db_session)

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
        form_snapshots=None,
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
            agent_results=make_scheduled_agent_results(
                evaluation_id,
                document_id,
                partial_without_curriculum=True,
            ),
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
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-model-fail@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    _seed_active_prompts(db_session)
    _seed_all_rubrics(db_session)
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
        form_snapshots=None,
        query_text=None,
        context=None,
        heartbeat_callback=None,
    ):
        if callable(heartbeat_callback):
            heartbeat_callback()
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=make_scheduled_agent_results(
                evaluation_id,
                document_id,
                partial_without_curriculum=True,
            ),
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
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-chunk-once@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    _seed_active_prompts(db_session)
    _seed_all_rubrics(db_session)

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
        form_snapshots=None,
        query_text=None,
        context=None,
        heartbeat_callback=None,
    ):
        if callable(heartbeat_callback):
            heartbeat_callback()
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=make_scheduled_agent_results(
                evaluation_id,
                document_id,
                partial_without_curriculum=True,
            ),
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
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    admin = create_user(
        db_session,
        name="Admin",
        email="admin-completes@lspu.edu.ph",
        password="password123",
        role=UserRole.ADMIN,
    )
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-layer3-empty@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )
    curriculum_id = _add_document(
        db_session, owner_id=admin.user_id, source_type="curriculum"
    )
    _seed_active_prompts(db_session)
    _seed_all_rubrics(db_session)

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
        confirmed_program="BSCS",
    )
    db_session.add(job)
    db_session.commit()

    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda *args, **kwargs: True,
    )

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
        form_snapshots=None,
        query_text=None,
        context=None,
        heartbeat_callback=None,
    ):
        if callable(heartbeat_callback):
            heartbeat_callback()
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=make_scheduled_agent_results(
                evaluation_id,
                document_id,
                partial_without_curriculum=False,
            ),
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
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    admin = create_user(
        db_session,
        name="Admin",
        email="admin-accidental-fail@lspu.edu.ph",
        password="password123",
        role=UserRole.ADMIN,
    )
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-accidental-fail@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )
    curriculum_id = _add_document(
        db_session, owner_id=admin.user_id, source_type="curriculum"
    )
    _seed_active_prompts(db_session)
    _seed_all_rubrics(db_session)

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
        confirmed_program="BSCS",
    )
    db_session.add(job)
    db_session.commit()

    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda *args, **kwargs: True,
    )

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
        form_snapshots=None,
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
                make_agent_result("sme", evaluation_id, document_id, success=True),
                make_agent_result("gad", evaluation_id, document_id, success=True),
                make_agent_result("itso", evaluation_id, document_id, success=True),
                make_agent_result(
                    "coordinator",
                    evaluation_id,
                    document_id,
                    success=False,
                    error_message=(
                        f"CoordinatorExecutionFailure (reference: {uuid4().hex[:16]})"
                    ),
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
    matrix_row = (
        db_session.query(MonitoringMatrix).filter_by(document_id=slm_id).first()
    )
    assert matrix_row is not None
    assert matrix_row.evaluation_status == "FAILED"


def test_four_terminal_cases_regression(db_session, monkeypatch) -> None:
    """Explicitly verify the four Phase 1B terminal truth cases:
    1) Intentional partial + all SME/GAD/ITSO success ->
       job COMPLETED, matrix COMPLETED_PARTIAL, partial intent.
    2) Intentional partial + required agent missing/failed ->
       job FAILED, matrix FAILED, partial intent.
    3) Full + all SME/GAD/ITSO/Coordinator success ->
       job COMPLETED, matrix COMPLETED, full intent.
    4) Full + curriculum unavailable or Coordinator missing/failed ->
       job FAILED, matrix FAILED, full intent.
    """
    from server.core import database as core_database
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from server.modules.synthesis.exceptions import EvaluationResultIntegrityError
    from server.modules.synthesis.models import MonitoringMatrix
    from server.modules.synthesis.service import get_evaluation_results
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner Four Cases",
        email="owner-four-cases@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    _seed_all_rubrics(db_session)
    db_session.commit()
    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    def _agent_result(name, eval_id, doc_id, success=True):
        return make_agent_result(
            name,
            eval_id,
            doc_id,
            success=success,
            default_score=3,
            summary="ok",
            model_name="test-model",
            processing_seconds=0.1,
            token_count=10,
            error_message=None
            if success
            else f"{name.capitalize()}ExecutionFailure (reference: {uuid4().hex[:16]})",
        )

    # --- Case 1: intentional partial + all SME/GAD/ITSO success ---
    slm_1 = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    job_1 = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_1,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        partial_without_curriculum=True,
        partial_reason="No curriculum available",
    )
    db_session.add(job_1)
    db_session.commit()

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        lambda self, **kwargs: SupervisorResult(
            evaluation_id=kwargs["evaluation_id"],
            document_id=kwargs["document_id"],
            agent_results=[
                _agent_result(
                    "sme", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
                _agent_result(
                    "gad", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
                _agent_result(
                    "itso", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
            ],
        ),
    )
    _run_claimed(job_1.evaluation_id, session_factory)
    db_session.expire_all()
    j1 = db_session.get(EvaluationJob, job_1.evaluation_id)
    assert j1.status == EvaluationStatus.COMPLETED.value
    assert j1.partial_without_curriculum is True
    m1 = db_session.query(MonitoringMatrix).filter_by(document_id=slm_1).one()
    assert m1.evaluation_status == "COMPLETED_PARTIAL"
    res1 = get_evaluation_results(job_1.evaluation_id, owner.user_id, db_session)
    assert res1.is_partial is True
    assert res1.partial_reason == "No curriculum available"
    assert res1.evaluation_status == EvaluationStatus.COMPLETED.value

    # --- Case 2: intentional partial + required agent failed ---
    slm_2 = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    job_2 = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_2,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        partial_without_curriculum=True,
        partial_reason="Deliberate partial",
    )
    db_session.add(job_2)
    db_session.commit()

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        lambda self, **kwargs: SupervisorResult(
            evaluation_id=kwargs["evaluation_id"],
            document_id=kwargs["document_id"],
            agent_results=[
                _agent_result(
                    "sme", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
                _agent_result(
                    "gad", kwargs["evaluation_id"], kwargs["document_id"], False
                ),
                _agent_result(
                    "itso", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
            ],
        ),
    )
    _run_claimed(job_2.evaluation_id, session_factory)
    db_session.expire_all()
    j2 = db_session.get(EvaluationJob, job_2.evaluation_id)
    assert j2.status == EvaluationStatus.FAILED.value
    assert j2.partial_without_curriculum is True
    assert "gad" in j2.error_message.lower()
    m2 = db_session.query(MonitoringMatrix).filter_by(document_id=slm_2).one()
    assert m2.evaluation_status == "FAILED"
    res2 = get_evaluation_results(job_2.evaluation_id, owner.user_id, db_session)
    assert res2.is_partial is True
    assert res2.partial_reason == "Deliberate partial"
    assert res2.evaluation_status == EvaluationStatus.FAILED.value

    # --- Case 3: full + all SME/GAD/ITSO/Coordinator success ---
    admin = create_user(
        db_session,
        name="Admin3",
        email=f"admin-case3-{uuid4().hex[:6]}@lspu.edu.ph",
        password="password123",
        role=UserRole.ADMIN,
    )
    db_session.commit()
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda *args, **kwargs: True,
    )
    slm_3 = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    syl_3 = _add_document(db_session, owner_id=owner.user_id, source_type="syllabus")
    cur_3 = _add_document(db_session, owner_id=admin.user_id, source_type="curriculum")
    job_3 = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_3,
        syllabus_id=syl_3,
        curriculum_id=cur_3,
        status=EvaluationStatus.SUBMITTED.value,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        confirmed_program="BSCS",
        partial_without_curriculum=False,
    )
    db_session.add(job_3)
    db_session.commit()

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        lambda self, **kwargs: SupervisorResult(
            evaluation_id=kwargs["evaluation_id"],
            document_id=kwargs["document_id"],
            agent_results=[
                _agent_result(
                    "sme", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
                _agent_result(
                    "coordinator", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
                _agent_result(
                    "gad", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
                _agent_result(
                    "itso", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
            ],
        ),
    )
    _run_claimed(job_3.evaluation_id, session_factory)
    db_session.expire_all()
    j3 = db_session.get(EvaluationJob, job_3.evaluation_id)
    assert j3.status == EvaluationStatus.COMPLETED.value
    assert j3.partial_without_curriculum is False
    m3 = db_session.query(MonitoringMatrix).filter_by(document_id=slm_3).one()
    assert m3.evaluation_status == "COMPLETED"
    res3 = get_evaluation_results(job_3.evaluation_id, owner.user_id, db_session)
    assert res3.is_partial is False
    assert res3.partial_reason is None
    assert res3.evaluation_status == EvaluationStatus.COMPLETED.value

    # --- Case 4: full + missing curriculum/coordinator -> never COMPLETED_PARTIAL
    slm_4 = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    job_4 = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_4,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        partial_without_curriculum=False,
    )
    db_session.add(job_4)
    db_session.commit()

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        lambda self, **kwargs: SupervisorResult(
            evaluation_id=kwargs["evaluation_id"],
            document_id=kwargs["document_id"],
            agent_results=[
                _agent_result(
                    "sme", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
                _agent_result(
                    "gad", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
                _agent_result(
                    "itso", kwargs["evaluation_id"], kwargs["document_id"], True
                ),
            ],
        ),
    )
    _run_claimed(job_4.evaluation_id, session_factory)
    db_session.expire_all()
    j4 = db_session.get(EvaluationJob, job_4.evaluation_id)
    assert j4.status == EvaluationStatus.FAILED.value
    assert j4.partial_without_curriculum is False
    m4 = db_session.query(MonitoringMatrix).filter_by(document_id=slm_4).one()
    assert m4.evaluation_status == "FAILED"
    assert m4.evaluation_status != "COMPLETED_PARTIAL"
    with pytest.raises(EvaluationResultIntegrityError):
        get_evaluation_results(job_4.evaluation_id, owner.user_id, db_session)


def test_resumed_evaluation_idempotency_truth(db_session, monkeypatch) -> None:
    """Resumed executions with existing AgentResult rows adhere to terminal truth:
    - Resumed intentional partial with 3 agents completes as COMPLETED_PARTIAL.
    - Resumed full run missing Coordinator fails as FAILED (never COMPLETED_PARTIAL).
    """
    from server.core import database as core_database
    from server.modules.synthesis.models import AgentResult, MonitoringMatrix
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner Resume",
        email="owner-resume@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    _seed_all_rubrics(db_session)
    db_session.commit()
    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    # 1. Resumed intentional partial with 3 existing AgentResults
    from server.modules.evaluations.agent_schedule import scheduled_agent_ids
    from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
    from server.modules.synthesis.service import persist_agent_outputs

    slm_partial = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    job_partial = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_partial,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        partial_without_curriculum=True,
        partial_reason="Resumed partial test",
    )
    db_session.add(job_partial)
    db_session.flush()

    resolve_or_reuse_evaluation_snapshots(
        db_session,
        job_partial.evaluation_id,
        scheduled_agent_ids(partial_without_curriculum=True),
    )

    partial_results = make_scheduled_agent_results(
        job_partial.evaluation_id,
        slm_partial,
        partial_without_curriculum=True,
    )
    persist_agent_outputs(
        db_session,
        job_partial.evaluation_id,
        slm_partial,
        partial_results,
        verify_ownership=lambda db: None,
    )
    db_session.commit()

    _run_claimed(job_partial.evaluation_id, session_factory)
    db_session.expire_all()
    refreshed_partial = db_session.get(EvaluationJob, job_partial.evaluation_id)
    assert refreshed_partial.status == EvaluationStatus.COMPLETED.value
    matrix_partial = (
        db_session.query(MonitoringMatrix).filter_by(document_id=slm_partial).one()
    )
    assert matrix_partial.evaluation_status == "COMPLETED_PARTIAL"

    # 2. Resumed full intent with 3 existing AgentResults (missing Coordinator)
    admin = create_user(
        db_session,
        name="AdminResume",
        email=f"admin-resume-{uuid4().hex[:6]}@lspu.edu.ph",
        password="password123",
        role=UserRole.ADMIN,
    )
    db_session.commit()
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda *args, **kwargs: True,
    )
    slm_full = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    cur_full = _add_document(
        db_session, owner_id=admin.user_id, source_type="curriculum"
    )
    job_full = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_full,
        syllabus_id=None,
        curriculum_id=cur_full,
        status=EvaluationStatus.SUBMITTED.value,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        confirmed_program="BSCS",
        partial_without_curriculum=False,
    )
    db_session.add(job_full)
    db_session.flush()

    full_snapshots = resolve_or_reuse_evaluation_snapshots(
        db_session,
        job_full.evaluation_id,
        scheduled_agent_ids(partial_without_curriculum=False),
    )
    full_snap_by_agent = {s.agent_id: s for s in full_snapshots}

    from server.modules.synthesis.result_integrity import build_persistable_agent_result

    for agent_name in ("sme", "gad", "itso"):
        res = make_agent_result(agent_name, job_full.evaluation_id, slm_full)
        dto = full_snap_by_agent[agent_name]
        p = build_persistable_agent_result(res, dto)
        ar = AgentResult(
            agent_result_id=uuid4(),
            evaluation_id=job_full.evaluation_id,
            document_id=slm_full,
            agent_name=agent_name,
            subtotal=p.subtotal,
            processing_seconds=p.processing_seconds,
            token_count=p.token_count,
            model_name=p.model_name,
            summary=p.summary,
            success=True,
            form_snapshot_id=dto.snapshot_id,
        )
        db_session.add(ar)
        db_session.flush()
        for s in p.criterion_scores:
            db_session.add(
                StoredCriterionScore(
                    criterion_score_id=uuid4(),
                    agent_result_id=ar.agent_result_id,
                    evaluation_id=job_full.evaluation_id,
                    document_id=slm_full,
                    criterion_id=s.criterion_id,
                    criterion_title=s.criterion_title,
                    score=s.score,
                    justification=s.justification,
                )
            )
    db_session.commit()

    _run_claimed(job_full.evaluation_id, session_factory)
    db_session.expire_all()
    refreshed_full = db_session.get(EvaluationJob, job_full.evaluation_id)
    assert refreshed_full.status == EvaluationStatus.FAILED.value
    matrix_full = (
        db_session.query(MonitoringMatrix).filter_by(document_id=slm_full).one()
    )
    assert matrix_full.evaluation_status == "FAILED"
    assert matrix_full.evaluation_status != "COMPLETED_PARTIAL"
