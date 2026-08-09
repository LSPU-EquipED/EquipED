"""Tests for evaluation execution ownership helpers and recovery.

These tests cover the minimal Phase 1 execution guard:
- atomic claim via ``acquire_evaluation_execution``
- token-aware status transitions
- terminal transitions clear ownership
- duplicate / wrong-token claims are safe no-ops
- the startup recovery helper clears stale tokens and re-queues
  interrupted jobs, and is idempotent at the supervisor level
  (existing AgentResult rows are preserved when outputs already exist)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from server.core.database import Base
from server.db.metadata import import_model_modules
from server.modules.admin.models import PromptVersion
from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.supervision.result import SupervisorResult
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.exceptions import (
    EvaluationExecutionOwnershipError,
    EvaluationPipelineFailure,
)
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import (
    recover_interrupted_evaluation_jobs,
    run_evaluation_job,
)
from server.modules.evaluations.service import (
    acquire_evaluation_execution,
    heartbeat_evaluation_execution,
    release_evaluation_execution,
    transition_evaluation_status,
)
from server.modules.synthesis.models import AgentResult
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _make_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_model_modules()
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _seed_active_prompts(session) -> None:
    for agent_id in ["sme", "coordinator", "gad", "itso"]:
        session.add(
            PromptVersion(
                agent_id=agent_id,
                version_number=1,
                prompt_text=f"{agent_id} prompt",
                is_active=True,
            )
        )
    session.commit()


def _add_document(session, *, owner_id, source_type: str) -> uuid.UUID:
    document_id = uuid4()
    session.add(
        Document(
            document_id=document_id,
            title=f"{source_type} doc",
            program="BSCS",
            source_type=source_type,
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=owner_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    session.add(
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=document_id,
            source_type=source_type,
            agent_domain="all",
            page_number=1,
            text=f"chunk for {source_type}",
            token_count=4,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    session.commit()
    return document_id


def _make_job(
    session,
    *,
    status: EvaluationStatus = EvaluationStatus.SUBMITTED,
    execution_token=None,
    execution_started_at=None,
    execution_heartbeat_at=None,
    document_id: uuid.UUID | None = None,
) -> EvaluationJob:
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=document_id if document_id is not None else uuid4(),
        syllabus_id=None,
        curriculum_id=None,
        status=status.value,
        error_message=None,
        submitted_by=uuid4(),
        submitted_at=datetime.now(UTC),
        completed_at=None,
        execution_token=execution_token,
        execution_started_at=execution_started_at,
        execution_heartbeat_at=execution_heartbeat_at,
    )
    session.add(job)
    session.commit()
    return job


# ---------------------------------------------------------------------------
# Service-layer / ownership tests
# ---------------------------------------------------------------------------


def test_only_one_runner_can_claim_a_job() -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        job = _make_job(session)

        token_a = uuid4()
        token_b = uuid4()
        assert acquire_evaluation_execution(session, job.evaluation_id, token_a) is True
        assert acquire_evaluation_execution(session, job.evaluation_id, token_b) is False  # noqa: E501

        session.expire_all()
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        assert refreshed.execution_token == token_a
    finally:
        session.close()


def test_terminal_jobs_cannot_be_claimed() -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        completed = _make_job(session, status=EvaluationStatus.COMPLETED)
        failed = _make_job(session, status=EvaluationStatus.FAILED)

        assert (
            acquire_evaluation_execution(session, completed.evaluation_id, uuid4())
            is False
        )
        assert (
            acquire_evaluation_execution(session, failed.evaluation_id, uuid4())
            is False
        )

        session.expire_all()
        assert (
            session.get(EvaluationJob, completed.evaluation_id).execution_token is None
        )
        assert (
            session.get(EvaluationJob, failed.evaluation_id).execution_token is None
        )
    finally:
        session.close()


def test_duplicate_runner_noops_when_already_claimed() -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        job = _make_job(session)
        token = uuid4()

        assert acquire_evaluation_execution(session, job.evaluation_id, token) is True
        # Second attempt with the same token is also a no-op (token is
        # not null, so the predicate excludes the row).
        assert acquire_evaluation_execution(session, job.evaluation_id, token) is False
        # Wrong token is also a no-op.
        assert (
            acquire_evaluation_execution(session, job.evaluation_id, uuid4()) is False
        )

        session.expire_all()
        assert session.get(EvaluationJob, job.evaluation_id).execution_token == token
    finally:
        session.close()


def test_transition_with_wrong_token_raises_controlled_error() -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        job = _make_job(session)
        owner_token = uuid4()
        other_token = uuid4()

        assert acquire_evaluation_execution(session, job.evaluation_id, owner_token) is True  # noqa: E501

        with pytest.raises(EvaluationExecutionOwnershipError):
            transition_evaluation_status(
                job.evaluation_id,
                EvaluationStatus.PREPROCESSING,
                session,
                execution_token=other_token,
            )

        session.expire_all()
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        # Status is unchanged; the row is still owned by the original token.
        assert refreshed.status == EvaluationStatus.SUBMITTED.value
        assert refreshed.execution_token == owner_token
    finally:
        session.close()


def test_transition_with_correct_token_succeeds() -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        job = _make_job(session)
        token = uuid4()
        assert acquire_evaluation_execution(session, job.evaluation_id, token) is True

        transition_evaluation_status(
            job.evaluation_id,
            EvaluationStatus.PREPROCESSING,
            session,
            execution_token=token,
        )

        session.expire_all()
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        assert refreshed.status == EvaluationStatus.PREPROCESSING.value
        # Non-terminal transition keeps the token.
        assert refreshed.execution_token == token
    finally:
        session.close()


def test_terminal_transition_clears_execution_token_fields() -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        job = _make_job(session, status=EvaluationStatus.SUBMITTED)
        token = uuid4()
        assert acquire_evaluation_execution(session, job.evaluation_id, token) is True
        # Progress through PREPROCESSING and EVALUATING to reach SYNTHESIZING
        transition_evaluation_status(
            job.evaluation_id, EvaluationStatus.PREPROCESSING, session, execution_token=token,  # noqa: E501
        )
        transition_evaluation_status(
            job.evaluation_id, EvaluationStatus.EVALUATING, session, execution_token=token,  # noqa: E501
        )
        transition_evaluation_status(
            job.evaluation_id, EvaluationStatus.SYNTHESIZING, session, execution_token=token,  # noqa: E501
        )

        transition_evaluation_status(
            job.evaluation_id,
            EvaluationStatus.COMPLETED,
            session,
            execution_token=token,
        )

        session.expire_all()
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        assert refreshed.status == EvaluationStatus.COMPLETED.value
        assert refreshed.execution_token is None
        assert refreshed.execution_started_at is None
        assert refreshed.execution_heartbeat_at is None
    finally:
        session.close()


def test_terminal_transition_to_failed_clears_execution_token_fields() -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        job = _make_job(session, status=EvaluationStatus.SUBMITTED)
        token = uuid4()
        assert acquire_evaluation_execution(session, job.evaluation_id, token) is True
        # Progress to EVALUATING before failing
        transition_evaluation_status(
            job.evaluation_id, EvaluationStatus.PREPROCESSING, session, execution_token=token,  # noqa: E501
        )
        transition_evaluation_status(
            job.evaluation_id, EvaluationStatus.EVALUATING, session, execution_token=token,  # noqa: E501
        )

        transition_evaluation_status(
            job.evaluation_id,
            EvaluationStatus.FAILED,
            session,
            execution_token=token,
            error_message="boom",
        )

        session.expire_all()
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        assert refreshed.status == EvaluationStatus.FAILED.value
        assert refreshed.execution_token is None
        assert refreshed.execution_started_at is None
        assert refreshed.execution_heartbeat_at is None
    finally:
        session.close()


def test_heartbeat_only_succeeds_for_matching_token() -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        job = _make_job(session)
        token = uuid4()
        assert acquire_evaluation_execution(session, job.evaluation_id, token) is True

        assert (
            heartbeat_evaluation_execution(session, job.evaluation_id, token) is True
        )
        assert (
            heartbeat_evaluation_execution(session, job.evaluation_id, uuid4())
            is False
        )
    finally:
        session.close()


def test_release_only_clears_for_matching_token() -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        job = _make_job(session)
        token = uuid4()
        assert acquire_evaluation_execution(session, job.evaluation_id, token) is True

        # Wrong token does not clear fields.
        assert (
            release_evaluation_execution(session, job.evaluation_id, uuid4()) is False
        )
        session.expire_all()
        assert session.get(EvaluationJob, job.evaluation_id).execution_token == token

        assert release_evaluation_execution(session, job.evaluation_id, token) is True
        session.expire_all()
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        assert refreshed.execution_token is None
        assert refreshed.execution_started_at is None
        assert refreshed.execution_heartbeat_at is None
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Orchestrator-level: failure path clears the execution token
# ---------------------------------------------------------------------------


def test_orchestrator_failure_clears_execution_token(monkeypatch) -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        owner_id = uuid4()
        document_id = _add_document(session, owner_id=owner_id, source_type="slm")
        _seed_active_prompts(session)
        job = _make_job(
            session,
            status=EvaluationStatus.SUBMITTED,
            document_id=document_id,
        )

        from server.core import database as core_database

        monkeypatch.setattr(core_database, "get_session_factory", lambda: SessionLocal)

        def boom_run_evaluation(self, **kwargs):
            raise RuntimeError("supervisor exploded")

        from server.modules.evaluations import orchestrator as orch

        monkeypatch.setattr(orch.Supervisor, "run_evaluation", boom_run_evaluation)

        with pytest.raises(EvaluationPipelineFailure) as exc_info:
            run_evaluation_job(job.evaluation_id)
        assert "supervisor exploded" not in str(exc_info.value)
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__suppress_context__ is True

        session.expire_all()
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        assert refreshed.status == EvaluationStatus.FAILED.value
        # FAILED transition must clear ownership so the job is no longer
        # locked, and so a later recovery can re-queue it if needed.
        assert refreshed.execution_token is None
        assert refreshed.execution_started_at is None
        assert refreshed.execution_heartbeat_at is None
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Recovery helper tests
# ---------------------------------------------------------------------------


def test_recovery_clears_and_requeues_non_terminal_jobs(monkeypatch) -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        owner_id = uuid4()
        _seed_active_prompts(session)
        # A non-terminal job whose previous runner crashed mid-flight.
        stale_token = uuid4()
        document_id = _add_document(session, owner_id=owner_id, source_type="slm")
        job = EvaluationJob(
            evaluation_id=uuid4(),
            document_id=document_id,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.EVALUATING.value,
            error_message=None,
            submitted_by=owner_id,
            submitted_at=datetime.now(UTC),
            completed_at=None,
            execution_token=stale_token,
            execution_started_at=datetime.now(UTC),
            execution_heartbeat_at=datetime.now(UTC),
        )
        session.add(job)

        # A terminal job that must NOT be touched.
        completed = _make_job(
            session,
            status=EvaluationStatus.COMPLETED,
            execution_token=None,
        )
        session.commit()

        from server.core import database as core_database

        monkeypatch.setattr(core_database, "get_session_factory", lambda: SessionLocal)

        from server.modules.evaluations import orchestrator as orch

        seen: list = []

        def fake_run(self, **kwargs):
            seen.append(kwargs.get("evaluation_id"))
            return SupervisorResult(
                evaluation_id=kwargs["evaluation_id"],
                document_id=kwargs["document_id"],
                agent_results=[
                    AgentEvaluationResult(
                        agent_name="sme",
                        evaluation_id=kwargs["evaluation_id"],
                        document_id=kwargs["document_id"],
                        subtotal=1,
                        criterion_scores=(
                            CriterionScore(
                                criterion_id="c1",
                                criterion_title="Criterion 1",
                                score=1,
                                justification="ok",
                            ),
                        ),
                        summary="ok",
                        model_name="local-model",
                        processing_seconds=0.1,
                        token_count=4,
                        success=True,
                        prompt_version_id=None,
                    )
                ],
            )

        monkeypatch.setattr(orch.Supervisor, "run_evaluation", fake_run)

        recovered = recover_interrupted_evaluation_jobs(SessionLocal)
        assert recovered == 1
        assert seen == [job.evaluation_id]

        session.expire_all()
        # The job ran to terminal; ownership was cleared by the terminal
        # transition, then no stale token remains.
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        assert refreshed.status == EvaluationStatus.COMPLETED.value
        assert refreshed.execution_token is None

        # Terminal job is untouched.
        terminal_row = session.get(EvaluationJob, completed.evaluation_id)
        assert terminal_row.status == EvaluationStatus.COMPLETED.value
        assert terminal_row.execution_token is None
    finally:
        session.close()


def test_recovery_does_not_duplicate_existing_agent_results(monkeypatch) -> None:
    """When AgentResult rows already exist for a job, recovery must skip
    the supervisor and resume from synthesis/finalization."""
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        owner_id = uuid4()
        _seed_active_prompts(session)
        document_id = _add_document(session, owner_id=owner_id, source_type="slm")

        evaluation_id = uuid4()
        stale_token = uuid4()
        job = EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.EVALUATING.value,
            error_message=None,
            submitted_by=owner_id,
            submitted_at=datetime.now(UTC),
            completed_at=None,
            execution_token=stale_token,
            execution_started_at=datetime.now(UTC),
            execution_heartbeat_at=datetime.now(UTC),
        )
        session.add(job)

        # Pre-existing AgentResult rows — the supervisor must NOT run again.
        existing = AgentResult(
            agent_result_id=uuid4(),
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_name="sme",
            subtotal=2.0,
            processing_seconds=0.1,
            token_count=4,
            model_name="local-model",
            summary="previous run",
            success=True,
        )
        session.add(existing)
        session.commit()

        from server.core import database as core_database
        from server.modules.evaluations import orchestrator as orch

        monkeypatch.setattr(core_database, "get_session_factory", lambda: SessionLocal)

        supervisor_calls: list = []

        def explode_if_called(self, **kwargs):
            supervisor_calls.append(kwargs.get("evaluation_id"))
            raise AssertionError(
                "Supervisor.run_evaluation should not be called when "
                "AgentResult rows already exist"
            )

        monkeypatch.setattr(orch.Supervisor, "run_evaluation", explode_if_called)

        recovered = recover_interrupted_evaluation_jobs(SessionLocal)
        assert recovered == 1
        assert supervisor_calls == []

        session.expire_all()
        # No duplicate AgentResult rows.
        assert (
            session.query(AgentResult)
            .filter_by(evaluation_id=evaluation_id)
            .count()
            == 1
        )
        refreshed = session.get(EvaluationJob, evaluation_id)
        assert refreshed.status == EvaluationStatus.COMPLETED.value
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Same-state idempotent no-op regression tests
# ---------------------------------------------------------------------------


def test_same_state_preprocessing_with_matching_token_is_noop() -> None:
    """Same-state PREPROCESSING transition with matching token must
    return the current state unchanged and preserve the token."""
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        job = _make_job(session, status=EvaluationStatus.PREPROCESSING)
        token = uuid4()
        # Manually claim ownership so the row has a matching token.
        session.execute(
            update(EvaluationJob)
            .where(EvaluationJob.evaluation_id == job.evaluation_id)
            .values(execution_token=token)
        )
        session.commit()
        session.expire_all()

        result = transition_evaluation_status(
            job.evaluation_id,
            EvaluationStatus.PREPROCESSING,
            session,
            execution_token=token,
        )
        assert result.status == EvaluationStatus.PREPROCESSING

        session.expire_all()
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        # Status unchanged.
        assert refreshed.status == EvaluationStatus.PREPROCESSING.value
        # Token NOT cleared or replaced.
        assert refreshed.execution_token == token
        # completed_at must NOT be set (not a terminal transition).
        assert refreshed.completed_at is None
    finally:
        session.close()


def test_same_state_with_wrong_token_still_rejected() -> None:
    """Same-state no-op path must still reject a mismatched token."""
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        job = _make_job(session, status=EvaluationStatus.PREPROCESSING)
        owner_token = uuid4()
        other_token = uuid4()
        session.execute(
            update(EvaluationJob)
            .where(EvaluationJob.evaluation_id == job.evaluation_id)
            .values(execution_token=owner_token)
        )
        session.commit()
        session.expire_all()

        with pytest.raises(EvaluationExecutionOwnershipError):
            transition_evaluation_status(
                job.evaluation_id,
                EvaluationStatus.PREPROCESSING,
                session,
                execution_token=other_token,
            )

        session.expire_all()
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        # Status and token fully preserved.
        assert refreshed.status == EvaluationStatus.PREPROCESSING.value
        assert refreshed.execution_token == owner_token
    finally:
        session.close()


def test_pre_claim_failure_does_not_transition(monkeypatch) -> None:
    """When an error occurs before the orchestrator acquires ownership,
    the exception handler must NOT call transition_evaluation_status —
    doing so without a matching token could clear another runner's token
    or steal ownership. The job stays in its current non-terminal state
    so the owner/retry logic can resolve it."""
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        owner_id = uuid4()
        document_id = _add_document(session, owner_id=owner_id, source_type="slm")
        _seed_active_prompts(session)
        job = _make_job(
            session,
            status=EvaluationStatus.SUBMITTED,
            document_id=document_id,
        )

        from server.core import database as core_database

        monkeypatch.setattr(core_database, "get_session_factory", lambda: SessionLocal)

        from server.modules.evaluations import orchestrator as orch_module

        def raise_before_acquire(db, evaluation_id, execution_token):
            raise RuntimeError("pre-claim failure")

        monkeypatch.setattr(
            orch_module, "acquire_evaluation_execution", raise_before_acquire
        )

        with pytest.raises(EvaluationPipelineFailure) as exc_info:
            run_evaluation_job(job.evaluation_id)
        assert "pre-claim failure" not in str(exc_info.value)
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__suppress_context__ is True

        session.expire_all()
        refreshed = session.get(EvaluationJob, job.evaluation_id)
        # Job must remain SUBMITTED — no unauthorized terminal transition.
        assert refreshed.status == EvaluationStatus.SUBMITTED.value
        assert refreshed.execution_token is None
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Recovery helper tests
# ---------------------------------------------------------------------------


def test_recovery_returns_zero_when_no_interrupted_jobs() -> None:
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        _make_job(session, status=EvaluationStatus.SUBMITTED, execution_token=None)
        _make_job(
            session,
            status=EvaluationStatus.COMPLETED,
            execution_token=None,
        )
        recovered = recover_interrupted_evaluation_jobs(SessionLocal)
        assert recovered == 0
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Regression tests: acquire only SUBMITTED, recovery catches tokenless
# ---------------------------------------------------------------------------


def test_acquire_only_allows_submitted() -> None:
    """acquire_evaluation_execution must reject PREPROCESSING, EVALUATING,
    SYNTHESIZING — only SUBMITTED jobs with null token are claimable."""
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        submitted = _make_job(session, status=EvaluationStatus.SUBMITTED)
        pre = _make_job(session, status=EvaluationStatus.PREPROCESSING)
        evaluating = _make_job(session, status=EvaluationStatus.EVALUATING)
        synthesizing = _make_job(session, status=EvaluationStatus.SYNTHESIZING)
        completed = _make_job(session, status=EvaluationStatus.COMPLETED)
        failed = _make_job(session, status=EvaluationStatus.FAILED)

        assert acquire_evaluation_execution(session, submitted.evaluation_id, uuid4()) is True  # noqa: E501
        assert acquire_evaluation_execution(session, pre.evaluation_id, uuid4()) is False  # noqa: E501
        assert acquire_evaluation_execution(session, evaluating.evaluation_id, uuid4()) is False  # noqa: E501
        assert acquire_evaluation_execution(session, synthesizing.evaluation_id, uuid4()) is False  # noqa: E501
        assert acquire_evaluation_execution(session, completed.evaluation_id, uuid4()) is False  # noqa: E501
        assert acquire_evaluation_execution(session, failed.evaluation_id, uuid4()) is False  # noqa: E501
    finally:
        session.close()


def test_recovery_finds_tokenless_evaluating(monkeypatch) -> None:
    """Recovery must find EVALUATING jobs even with NULL execution_token
    (the scenario where a crash happened during a status transition that
    cleared the token but before reaching a terminal state)."""
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        owner_id = uuid4()
        _seed_active_prompts(session)
        document_id = _add_document(session, owner_id=owner_id, source_type="slm")

        # Tokenless EVALUATING — the core regression case.
        tokenless_stuck = EvaluationJob(
            evaluation_id=uuid4(),
            document_id=document_id,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.EVALUATING.value,
            error_message="Previous transient error",
            submitted_by=owner_id,
            submitted_at=datetime.now(UTC),
            completed_at=None,
            execution_token=None,
            execution_started_at=None,
            execution_heartbeat_at=None,
        )
        session.add(tokenless_stuck)

        # Token-bearing EVALUATING — classic stale runner case.
        stale_token = uuid4()
        token_stuck = EvaluationJob(
            evaluation_id=uuid4(),
            document_id=document_id,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.EVALUATING.value,
            error_message=None,
            submitted_by=owner_id,
            submitted_at=datetime.now(UTC),
            completed_at=None,
            execution_token=stale_token,
            execution_started_at=datetime.now(UTC),
            execution_heartbeat_at=datetime.now(UTC),
        )
        session.add(token_stuck)

        # Clean SUBMITTED — must not be recovered.
        clean = EvaluationJob(
            evaluation_id=uuid4(),
            document_id=document_id,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.SUBMITTED.value,
            error_message=None,
            submitted_by=owner_id,
            submitted_at=datetime.now(UTC),
            completed_at=None,
            execution_token=None,
        )
        session.add(clean)

        # Terminal COMPLETED — must not be touched.
        terminal = EvaluationJob(
            evaluation_id=uuid4(),
            document_id=document_id,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.COMPLETED.value,
            error_message=None,
            submitted_by=owner_id,
            submitted_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            execution_token=None,
        )
        session.add(terminal)
        session.commit()

        from server.core import database as core_database
        from server.modules.evaluations import orchestrator as orch

        monkeypatch.setattr(core_database, "get_session_factory", lambda: SessionLocal)

        seen: list = []

        def fake_run(self, **kwargs):
            seen.append(kwargs.get("evaluation_id"))
            return SupervisorResult(
                evaluation_id=kwargs["evaluation_id"],
                document_id=kwargs["document_id"],
                agent_results=[
                    AgentEvaluationResult(
                        agent_name="sme",
                        evaluation_id=kwargs["evaluation_id"],
                        document_id=kwargs["document_id"],
                        subtotal=1,
                        criterion_scores=(
                            CriterionScore(
                                criterion_id="c1",
                                criterion_title="Criterion 1",
                                score=1,
                                justification="ok",
                            ),
                        ),
                        summary="ok",
                        model_name="local-model",
                        processing_seconds=0.1,
                        token_count=4,
                        success=True,
                        prompt_version_id=None,
                    )
                ],
            )

        monkeypatch.setattr(orch.Supervisor, "run_evaluation", fake_run)

        recovered = recover_interrupted_evaluation_jobs(SessionLocal)
        # Both tokenless and token-bearing stuck jobs should be recovered.
        assert recovered == 2
        assert tokenless_stuck.evaluation_id in seen
        assert token_stuck.evaluation_id in seen

        session.expire_all()

        # Tokenless stuck: reset to clean SUBMITTED, then ran to terminal.
        refreshed_tokenless = session.get(EvaluationJob, tokenless_stuck.evaluation_id)
        assert refreshed_tokenless.status == EvaluationStatus.COMPLETED.value
        assert refreshed_tokenless.execution_token is None
        # Prior transient error must be cleared.
        assert refreshed_tokenless.error_message is None

        # Token-bearing stuck: same.
        refreshed_token = session.get(EvaluationJob, token_stuck.evaluation_id)
        assert refreshed_token.status == EvaluationStatus.COMPLETED.value
        assert refreshed_token.execution_token is None

        # Clean SUBMITTED: untouched.
        refreshed_clean = session.get(EvaluationJob, clean.evaluation_id)
        assert refreshed_clean.status == EvaluationStatus.SUBMITTED.value

        # Terminal COMPLETED: untouched.
        refreshed_terminal = session.get(EvaluationJob, terminal.evaluation_id)
        assert refreshed_terminal.status == EvaluationStatus.COMPLETED.value
    finally:
        session.close()


def test_recovery_preserves_agent_results_on_tokenless_recovery(monkeypatch) -> None:
    """When AgentResult rows already exist for a tokenless stuck job,
    recovery must skip the supervisor and resume from synthesis, producing
    no duplicate AgentResult rows."""
    SessionLocal = _make_session_factory()
    session = SessionLocal()
    try:
        owner_id = uuid4()
        _seed_active_prompts(session)
        document_id = _add_document(session, owner_id=owner_id, source_type="slm")

        evaluation_id = uuid4()
        job = EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.EVALUATING.value,
            error_message="timed out",
            submitted_by=owner_id,
            submitted_at=datetime.now(UTC),
            completed_at=None,
            execution_token=None,
        )
        session.add(job)

        # Pre-existing AgentResult rows — must survive recovery.
        existing = AgentResult(
            agent_result_id=uuid4(),
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_name="sme",
            subtotal=2.0,
            processing_seconds=0.1,
            token_count=4,
            model_name="local-model",
            summary="previous run",
            success=True,
        )
        session.add(existing)
        session.commit()

        from server.core import database as core_database
        from server.modules.evaluations import orchestrator as orch

        monkeypatch.setattr(core_database, "get_session_factory", lambda: SessionLocal)

        supervisor_calls: list = []

        def explode_if_called(self, **kwargs):
            supervisor_calls.append(kwargs.get("evaluation_id"))
            raise AssertionError(
                "Supervisor.run_evaluation should not be called when "
                "AgentResult rows already exist"
            )

        monkeypatch.setattr(orch.Supervisor, "run_evaluation", explode_if_called)

        recovered = recover_interrupted_evaluation_jobs(SessionLocal)
        assert recovered == 1
        assert supervisor_calls == []

        session.expire_all()
        # No duplicate AgentResult rows.
        assert (
            session.query(AgentResult)
            .filter_by(evaluation_id=evaluation_id)
            .count()
            == 1
        )
        refreshed = session.get(EvaluationJob, evaluation_id)
        assert refreshed.status == EvaluationStatus.COMPLETED.value
        assert refreshed.error_message is None
    finally:
        session.close()
