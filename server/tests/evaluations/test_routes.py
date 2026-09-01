"""Router/TestClient integration tests for evaluations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus

from .conftest import _add_document, _seed_active_prompts


def test_no_api_path_can_fake_completed(
    client: TestClient, db_session, monkeypatch
) -> None:
    from server.modules.evaluations import router as evaluations_router

    faculty = create_user(
        db_session,
        name="Faculty User",
        email="faculty-eval@lspu.edu.ph",
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
        email="faculty-lifecycle@lspu.edu.ph",
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
        email="owner-router@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email="other-router@lspu.edu.ph",
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
        email="faculty-results-partial@lspu.edu.ph",
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
        is_pre_snapshot_legacy=True,
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


def test_latest_evaluations_endpoint_returns_latest_and_dedupes(
    client: TestClient, db_session
) -> None:
    faculty = create_user(
        db_session,
        name="Faculty Latest",
        email="faculty-latest-route@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc_1 = _add_document(db_session, owner_id=faculty.user_id, source_type="slm")
    doc_2 = _add_document(db_session, owner_id=faculty.user_id, source_type="slm")

    t0 = datetime.now(UTC) - timedelta(minutes=10)
    t1 = datetime.now(UTC)

    # doc 1: 2 jobs (old FAILED, new COMPLETED)
    job_1_old = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_1,
        status=EvaluationStatus.FAILED.value,
        submitted_by=faculty.user_id,
        submitted_at=t0,
        completed_at=t0,
        error_message="timeout",
    )
    job_1_new = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_1,
        status=EvaluationStatus.COMPLETED.value,
        submitted_by=faculty.user_id,
        submitted_at=t1,
        completed_at=t1,
        error_message=None,
    )
    # doc 2: 1 job
    job_2 = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_2,
        status=EvaluationStatus.SUBMITTED.value,
        submitted_by=faculty.user_id,
        submitted_at=t1,
        completed_at=None,
    )
    db_session.add_all([job_1_old, job_1_new, job_2])
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    # Pass doc_1 duplicated and doc_2
    response = client.get(
        f"/api/v1/evaluations/latest?document_id={doc_1}&document_id={doc_2}&document_id={doc_1}"
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2

    by_doc = {item["document_id"]: item for item in data["items"]}
    assert by_doc[str(doc_1)]["evaluation_id"] == str(job_1_new.evaluation_id)
    assert by_doc[str(doc_1)]["status"] == "COMPLETED"
    assert by_doc[str(doc_1)]["error_message"] is None
    assert by_doc[str(doc_1)]["completed_at"] is not None

    assert by_doc[str(doc_2)]["evaluation_id"] == str(job_2.evaluation_id)
    assert by_doc[str(doc_2)]["status"] == "SUBMITTED"
    assert by_doc[str(doc_2)]["completed_at"] is None


def test_latest_evaluations_endpoint_empty_and_unknown(
    client: TestClient, db_session
) -> None:
    faculty = create_user(
        db_session,
        name="Faculty Empty",
        email="faculty-empty-latest@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    # No document_id query param
    resp_empty = client.get("/api/v1/evaluations/latest")
    assert resp_empty.status_code == 200
    assert resp_empty.json() == {"items": []}

    # Unknown document_id query param
    resp_unknown = client.get(f"/api/v1/evaluations/latest?document_id={uuid4()}")
    assert resp_unknown.status_code == 200
    assert resp_unknown.json() == {"items": []}


def test_latest_evaluations_endpoint_max_limit(client: TestClient, db_session) -> None:
    faculty = create_user(
        db_session,
        name="Faculty Max",
        email="faculty-max-latest@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    # 101 distinct UUIDs -> 422
    distinct_params = "&".join(f"document_id={uuid4().hex[:6]}" for _ in range(101))
    resp_over = client.get(f"/api/v1/evaluations/latest?{distinct_params}")
    assert resp_over.status_code == 422

    # 105 duplicated UUIDs (only 2 distinct) -> 200
    id1 = uuid4()
    id2 = uuid4()
    dup_params = "&".join(
        f"document_id={id1 if i % 2 == 0 else id2}" for i in range(105)
    )
    resp_dup = client.get(f"/api/v1/evaluations/latest?{dup_params}")
    assert resp_dup.status_code == 200
    assert resp_dup.json() == {"items": []}


def test_latest_evaluations_endpoint_ownership_isolation(
    client: TestClient, db_session
) -> None:
    user1 = create_user(
        db_session,
        name="User One",
        email="user1-latest@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    user2 = create_user(
        db_session,
        name="User Two",
        email="user2-latest@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc_u2 = _add_document(db_session, owner_id=user2.user_id, source_type="slm")
    job_u2 = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_u2,
        status=EvaluationStatus.COMPLETED.value,
        submitted_by=user2.user_id,
        submitted_at=datetime.now(UTC),
    )
    db_session.add(job_u2)
    db_session.commit()

    # User 1 logs in and queries for User 2's document ID
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user1.email, "password": "password123"},
    )
    assert login.status_code == 200

    response = client.get(f"/api/v1/evaluations/latest?document_id={doc_u2}")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_dynamic_evaluation_route_unaffected(client: TestClient, db_session) -> None:
    faculty = create_user(
        db_session,
        name="Faculty Dynamic",
        email="faculty-dynamic-check@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc_id = _add_document(db_session, owner_id=faculty.user_id, source_type="slm")
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_id,
        status=EvaluationStatus.SUBMITTED.value,
        submitted_by=faculty.user_id,
        submitted_at=datetime.now(UTC),
    )
    db_session.add(job)
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    # Dynamic route /{evaluation_id} returns the job
    resp = client.get(f"/api/v1/evaluations/{job.evaluation_id}")
    assert resp.status_code == 200
    assert resp.json()["evaluation_id"] == str(job.evaluation_id)


@pytest.mark.parametrize(
    ("setup_kind", "chroma_ready"),
    [
        ("non_existent", True),
        ("wrong_source_type", True),
        ("missing_uploader_user", True),
        ("non_admin_uploader", True),
        ("program_mismatch", True),
        ("pending_status", True),
        ("failed_status", True),
        ("no_chunks", True),
        ("no_chroma_vectors", False),
    ],
)
def test_submit_evaluation_unready_curriculum_route_parameterized(
    client: TestClient, db_session, monkeypatch, setup_kind: str, chroma_ready: bool
) -> None:
    from server.modules.evaluations import router as evaluations_router

    monkeypatch.setattr(evaluations_router, "probe_local_model_readiness", lambda: None)
    monkeypatch.setattr(evaluations_router, "admission_schema_ready", lambda db: True)
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: chroma_ready,
    )

    admin = create_user(
        db_session,
        name="Admin Route",
        email=f"admin-route-{uuid4().hex[:6]}@lspu.edu.ph",
        password="password123",
        role=UserRole.ADMIN,
    )
    faculty = create_user(
        db_session,
        name="Faculty Route",
        email=f"faculty-route-{uuid4().hex[:6]}@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=faculty.user_id, source_type="slm")

    if setup_kind == "non_existent":
        curriculum_id = uuid4()
    elif setup_kind == "wrong_source_type":
        curriculum_id = _add_document(
            db_session, owner_id=admin.user_id, source_type="syllabus"
        )
    elif setup_kind == "missing_uploader_user":
        curriculum_id = _add_document(
            db_session, owner_id=uuid4(), source_type="curriculum"
        )
    elif setup_kind == "non_admin_uploader":
        curriculum_id = _add_document(
            db_session, owner_id=faculty.user_id, source_type="curriculum"
        )
    elif setup_kind == "program_mismatch":
        curriculum_id = _add_document(
            db_session, owner_id=admin.user_id, source_type="curriculum"
        )
        curr_doc = db_session.get(Document, curriculum_id)
        curr_doc.program = "BSInfoTech"
        db_session.commit()
    elif setup_kind == "pending_status":
        curriculum_id = _add_document(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            processing_status="PENDING",
        )
    elif setup_kind == "failed_status":
        curriculum_id = _add_document(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            processing_status="FAILED",
        )
    elif setup_kind == "no_chunks":
        curriculum_id = _add_document(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            with_chunks=False,
        )
    elif setup_kind == "no_chroma_vectors":
        curriculum_id = _add_document(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            chroma_stored=False,
        )
    else:
        pytest.fail(f"Unknown setup_kind: {setup_kind}")

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    resp = client.post(
        "/api/v1/evaluations/",
        json={
            "document_id": str(slm_id),
            "curriculum_id": str(curriculum_id),
            "partial_without_curriculum": False,
            "confirmed_program": "BSCS",
        },
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "Curriculum is not ready for evaluation."
    assert db_session.query(EvaluationJob).count() == 0


def test_submit_evaluation_slm_404_masking_precedes_curriculum_validation(
    client: TestClient, db_session, monkeypatch
) -> None:
    """Foreign/missing target SLM returns 404 before curriculum readiness check."""
    from server.modules.evaluations import router as evaluations_router

    monkeypatch.setattr(evaluations_router, "probe_local_model_readiness", lambda: None)
    monkeypatch.setattr(evaluations_router, "admission_schema_ready", lambda db: True)

    other_user = create_user(
        db_session,
        name="Other Faculty",
        email="other-fac@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    faculty = create_user(
        db_session,
        name="Submitter Faculty",
        email="submitter-fac@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    # Foreign SLM document
    foreign_slm_id = _add_document(
        db_session, owner_id=other_user.user_id, source_type="slm"
    )

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    # Unready curriculum + foreign SLM -> must return 404, not 422
    resp = client.post(
        "/api/v1/evaluations/",
        json={
            "document_id": str(foreign_slm_id),
            "curriculum_id": str(uuid4()),
            "partial_without_curriculum": False,
            "confirmed_program": "BSCS",
        },
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found."
    assert db_session.query(EvaluationJob).count() == 0
