"""Router/TestClient integration tests for evaluations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus

from .conftest import _add_document, _seed_active_prompts


def test_no_api_path_can_fake_completed(
    client: TestClient, db_session, monkeypatch
) -> None:
    from server.modules.evaluations import router as evaluations_router

    faculty = create_user(
        db_session,
        name="Faculty User",
        email="faculty-eval@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=faculty.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session, owner_id=faculty.user_id, source_type="syllabus"
    )
    _seed_active_prompts(db_session)

    monkeypatch.setattr(evaluations_router, "probe_local_model_readiness", lambda: None)
    monkeypatch.setattr(evaluations_router, "admission_schema_ready", lambda db: True)
    drain_calls: list[object] = []
    monkeypatch.setattr(
        evaluations_router,
        "drain_evaluation_queue",
        lambda: drain_calls.append(True),
    )

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/v1/evaluations/",
        json={
            "document_id": str(slm_id),
            "syllabus_id": str(syllabus_id),
            "partial_without_curriculum": True,
            "confirmed_program": "BSCS",
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "SUBMITTED"
    job = db_session.query(EvaluationJob).one()
    assert job.status == EvaluationStatus.SUBMITTED.value
    assert len(drain_calls) == 1


def test_submit_evaluation_runs_honest_lifecycle_to_failed(
    client: TestClient, db_session, monkeypatch
) -> None:
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from server.modules.evaluations import router as evaluations_router
    from sqlalchemy.orm import sessionmaker

    faculty = create_user(
        db_session,
        name="Faculty User",
        email="faculty-lifecycle@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=faculty.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session, owner_id=faculty.user_id, source_type="syllabus"
    )
    _seed_active_prompts(db_session)

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
                )
            ],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        fake_run_evaluation,
    )

    monkeypatch.setattr(evaluations_router, "probe_local_model_readiness", lambda: None)
    monkeypatch.setattr(evaluations_router, "admission_schema_ready", lambda db: True)
    real_drain = evaluation_orchestrator.drain_evaluation_queue
    drain_calls: list[object] = []

    def run_queue():
        drain_calls.append(True)
        real_drain(session_factory)

    monkeypatch.setattr(evaluations_router, "drain_evaluation_queue", run_queue)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/v1/evaluations/",
        json={
            "document_id": str(slm_id),
            "syllabus_id": str(syllabus_id),
            "partial_without_curriculum": True,
            "confirmed_program": "BSCS",
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "SUBMITTED"

    job = db_session.query(EvaluationJob).one()
    assert job.status == EvaluationStatus.FAILED.value
    assert seen_statuses[-1] == EvaluationStatus.FAILED
    assert job.error_message is not None
    assert job.completed_at is not None
    assert len(drain_calls) == 1


def test_router_masks_foreign_access_for_all_roles(
    client: TestClient, db_session
) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-router@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email="other-router@example.com",
        password="password456",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        syllabus_id=uuid4(),
        curriculum_id=uuid4(),
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(job)
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": other.email, "password": "password456"},
    )
    assert login.status_code == 200

    assert client.get(f"/api/v1/evaluations/{job.evaluation_id}").status_code == 404
    assert (
        client.get(f"/api/v1/evaluations/{job.evaluation_id}/status").status_code == 404
    )


def test_results_partial_without_curriculum_returns_partial_reason(
    client: TestClient, db_session, monkeypatch
) -> None:
    """Successful no-curriculum partial evaluation results return is_partial=True,
    partial_reason present, and Coordinator absent from active_agents."""
    from server.modules.synthesis.models import AgentResult

    faculty = create_user(
        db_session,
        name="Faculty User",
        email="faculty-results-partial@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=faculty.user_id, source_type="slm")

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_id,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.COMPLETED.value,
        error_message=None,
        submitted_by=faculty.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        partial_without_curriculum=True,
        partial_reason="No curriculum reference was available; Coordinator review was skipped.",  # noqa: E501
    )
    db_session.add(job)
    db_session.flush()

    # Persist AgentResult rows for SME, GAD, ITSO only — no Coordinator
    for agent_name in ("sme", "gad", "itso"):
        db_session.add(
            AgentResult(
                agent_result_id=uuid4(),
                evaluation_id=job.evaluation_id,
                document_id=slm_id,
                agent_name=agent_name,
                subtotal=3.0,
                processing_seconds=0.1,
                token_count=5,
                model_name="test-model",
                summary=f"{agent_name} evaluation",
                success=True,
            )
        )
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/results")
    assert response.status_code == 200
    data = response.json()

    assert data["is_partial"] is True
    assert data["partial_reason"] is not None
    assert "curriculum" in data["partial_reason"].lower()
    assert "coordinator" not in data["active_agents"]
    assert set(data["active_agents"]) == {"sme", "gad", "itso"}
    assert data["failed_agents"] == []
