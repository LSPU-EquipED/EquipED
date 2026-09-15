"""Targeted single-agent orchestrator tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.agent_schedule import scheduled_agent_ids
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.synthesis.models import MonitoringMatrix
from server.tests.evaluations.conftest import (
    _add_document,
    _seed_active_prompts,
    _seed_all_rubrics,
)
from server.tests.evaluations.snapshot_test_helpers import make_agent_result


def _run_claimed(evaluation_id, session_factory):
    from server.modules.evaluations import orchestrator as orch

    token = uuid4()

    session = session_factory()
    try:
        job = session.get(EvaluationJob, evaluation_id)
        job.status = EvaluationStatus.PREPROCESSING.value
        job.admission_slot = 1
        job.execution_token = token
        from datetime import UTC as _UTC
        from datetime import datetime as _dt

        job.execution_started_at = _dt.now(_UTC)
        job.execution_heartbeat_at = _dt.now(_UTC)
        session.commit()
    finally:
        session.close()
    orch._execute_claimed_evaluation(evaluation_id, token, session_factory)


def test_scheduled_agent_ids_single_target() -> None:
    assert scheduled_agent_ids(target_agent="gad") == ("gad",)
    assert scheduled_agent_ids(target_agent="sme") == ("sme",)
    assert scheduled_agent_ids(target_agent="all") == (
        "sme",
        "coordinator",
        "gad",
        "itso",
    )


def test_orchestrator_single_gad_dispatches_only_gad(db_session, monkeypatch) -> None:
    from server.core import database as core_database
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.evaluations import orchestrator as orch
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-single-gad@lspu.edu.ph",
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
        status=EvaluationStatus.SUBMITTED.value,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        target_agent="gad",
        partial_without_curriculum=False,
        confirmed_program="BSCS",
    )
    db_session.add(job)
    db_session.commit()

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    captured: list[str] = []

    def fake_run(self, **kwargs):
        captured.extend(
            [getattr(a, "agent_name", type(a).__name__) for a in self.agents]
        )
        if callable(kwargs.get("heartbeat_callback")):
            kwargs["heartbeat_callback"]()
        return SupervisorResult(
            evaluation_id=kwargs["evaluation_id"],
            document_id=kwargs["document_id"],
            agent_results=[
                make_agent_result(
                    "gad",
                    kwargs["evaluation_id"],
                    kwargs["document_id"],
                )
            ],
        )

    monkeypatch.setattr(orch.Supervisor, "run_evaluation", fake_run)

    _run_claimed(job.evaluation_id, session_factory)

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.COMPLETED.value
    assert captured == ["gad"]
    matrix_row = db_session.query(MonitoringMatrix).filter_by(document_id=slm_id).one()
    assert matrix_row.evaluation_status == "IN_PROGRESS"
    assert set(matrix_row.domain_scores_json.keys()) == {"gad"}
