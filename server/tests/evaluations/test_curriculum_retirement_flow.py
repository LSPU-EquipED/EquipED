"""Backend regression tests for curriculum retirement flow."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from fastapi.testclient import TestClient

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.synthesis.models import AgentResult

from .conftest import _add_document, _seed_active_prompts


def _login(client: TestClient, db_session, role: UserRole):
    user = create_user(
        db_session,
        name=f"Test {role.value}",
        email=f"user_{uuid.uuid4().hex[:6]}@example.com",
        password="password123",
        role=role,
    )
    db_session.commit()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    )
    assert resp.status_code == 200
    return user


def test_upload_rbac_and_retired_source_types(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    """Faculty SLM only; Admin syllabus/policy; curriculum/rubric PDFs rejected."""
    import server.modules.documents.service as doc_service
    monkeypatch.setattr(doc_service, "ingest_document", lambda *args, **kwargs: [])

    _login(client, db_session, UserRole.FACULTY)

    # Faculty trying syllabus -> forbidden (403)
    resp = client.post(
        "/api/v1/documents/upload",
        data={"source_type": "syllabus", "title": "Syllabus"},
        files={"file": ("sys.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert resp.status_code == 403

    # Faculty trying direct curriculum -> forbidden (403)
    resp = client.post(
        "/api/v1/documents/upload",
        data={"source_type": "curriculum", "title": "Curriculum", "program": "BSCS"},
        files={"file": ("curr.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert resp.status_code in (403, 422)

    # Admin trying direct curriculum -> unprocessable (422)
    _login(client, db_session, UserRole.ADMIN)
    resp = client.post(
        "/api/v1/documents/upload",
        data={"source_type": "curriculum", "title": "Curriculum", "program": "BSCS"},
        files={"file": ("curr.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert resp.status_code == 422

    # Admin trying rubric PDF -> unprocessable (422)
    resp = client.post(
        "/api/v1/documents/upload",
        data={"source_type": "rubric_sme", "title": "Rubric"},
        files={"file": ("rubric.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert resp.status_code == 422


def test_admin_slm_upload_retained_for_model_validation(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    """Admin SLM upload remains available for Model Validation."""
    import server.modules.documents.service as doc_service
    monkeypatch.setattr(doc_service, "ingest_document", lambda *args, **kwargs: [])

    _login(client, db_session, UserRole.ADMIN)
    resp = client.post(
        "/api/v1/documents/upload",
        data={
            "source_type": "slm",
            "title": "Admin SLM",
            "program": "BSCS",
        },
        files={"file": ("slm.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert resp.status_code == 201


def test_submit_evaluation_requires_partial_and_confirmed_program(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    """Direct submission without partial_without_curriculum=True or confirmed_program rejected."""
    from server.modules.evaluations import router as evaluations_router
    monkeypatch.setattr(evaluations_router, "run_evaluation_job", lambda *args, **kwargs: None)

    faculty_user = _login(client, db_session, UserRole.FACULTY)

    slm = Document(
        document_id=uuid.uuid4(),
        title="SLM Document",
        program="BSCS",
        source_type="slm",
        file_path="uploads/slm.pdf",
        uploaded_by=faculty_user.user_id,
        processing_status="PROCESSED",
        evaluation_readiness="READY",
    )
    chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=slm.document_id,
        source_type="slm",
        agent_domain="all",
        page_number=1,
        text="SLM text content",
        token_count=5,
        chroma_stored=False,
    )
    curr_doc = Document(
        document_id=uuid.uuid4(),
        title="Curriculum Document",
        program="BSCS",
        source_type="curriculum",
        file_path="uploads/curr.pdf",
        uploaded_by=faculty_user.user_id,
        processing_status="PROCESSED",
        evaluation_readiness="READY",
    )
    db_session.add_all([slm, chunk, curr_doc])
    db_session.commit()

    # Missing partial_without_curriculum=True -> 422
    resp = client.post(
        "/api/v1/evaluations/",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": False,
            "confirmed_program": "BSCS",
        },
    )
    assert resp.status_code == 422

    # Missing confirmed_program -> 422
    resp = client.post(
        "/api/v1/evaluations/",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
        },
    )
    assert resp.status_code == 422

    # Attempting to supply curriculum_id -> 422
    resp = client.post(
        "/api/v1/evaluations/",
        json={
            "document_id": str(slm.document_id),
            "curriculum_id": str(curr_doc.document_id),
            "partial_without_curriculum": True,
            "confirmed_program": "BSCS",
        },
    )
    assert resp.status_code == 422

    # Valid submission -> 202
    resp = client.post(
        "/api/v1/evaluations/",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "confirmed_program": "BSCS",
        },
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["partial_without_curriculum"] is True
    assert data["curriculum_id"] is None


def test_supervisor_excludes_coordinator_and_synthesizes_partial(
    client: TestClient,
    db_session,
) -> None:
    """Supervisor execution skips Coordinator and synthesis produces partial matrix status."""
    faculty_user = _login(client, db_session, UserRole.FACULTY)

    slm = Document(
        document_id=uuid.uuid4(),
        title="SLM Document",
        program="BSCS",
        source_type="slm",
        file_path="uploads/slm.pdf",
        uploaded_by=faculty_user.user_id,
        processing_status="PROCESSED",
        evaluation_readiness="READY",
    )
    chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=slm.document_id,
        source_type="slm",
        agent_domain="all",
        page_number=1,
        text="SLM text content",
        token_count=5,
        chroma_stored=False,
    )
    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=slm.document_id,
        status=EvaluationStatus.SUBMITTED.value,
        partial_without_curriculum=True,
        partial_reason="Curriculum evaluation flow retired",
        submitted_by=faculty_user.user_id,
    )
    db_session.add_all([slm, chunk, job])
    db_session.commit()

    res_sme = AgentResult(
        agent_result_id=uuid.uuid4(),
        evaluation_id=job.evaluation_id,
        document_id=slm.document_id,
        agent_name="sme",
        model_name="mock-model",
        success=True,
        subtotal=3.5,
    )
    res_gad = AgentResult(
        agent_result_id=uuid.uuid4(),
        evaluation_id=job.evaluation_id,
        document_id=slm.document_id,
        agent_name="gad",
        model_name="mock-model",
        success=True,
        subtotal=4.0,
    )
    res_itso = AgentResult(
        agent_result_id=uuid.uuid4(),
        evaluation_id=job.evaluation_id,
        document_id=slm.document_id,
        agent_name="itso",
        model_name="mock-model",
        success=True,
        subtotal=3.8,
    )
    db_session.add_all([res_sme, res_gad, res_itso])
    db_session.commit()

    from server.modules.synthesis.matrix import compute_synthesized_score
    synthesis = compute_synthesized_score(
        [res_sme, res_gad, res_itso],
        force_partial=job.partial_without_curriculum,
        partial_reason=job.partial_reason,
    )
    assert synthesis["is_partial"] is True
    assert "coordinator" not in synthesis["active_agents"]


def test_historical_evaluations_preserved_with_cleared_curriculum_fk(
    client: TestClient,
    db_session,
) -> None:
    """Historical evaluation job details remain accessible even if curriculum_id is None or purged."""
    faculty_user = _login(client, db_session, UserRole.FACULTY)

    slm = Document(
        document_id=uuid.uuid4(),
        title="Historical SLM",
        program="BSCS",
        source_type="slm",
        file_path="uploads/historical_slm.pdf",
        uploaded_by=faculty_user.user_id,
        processing_status="PROCESSED",
        evaluation_readiness="READY",
    )
    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=slm.document_id,
        curriculum_id=None,  # cleared link
        status=EvaluationStatus.COMPLETED.value,
        partial_without_curriculum=False,  # was historical full evaluation
        submitted_by=faculty_user.user_id,
    )
    db_session.add_all([slm, job])
    db_session.commit()

    resp = client.get(f"/api/v1/evaluations/{job.evaluation_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_id"] == str(job.evaluation_id)
    assert data["curriculum_id"] is None
    assert data["status"] == "COMPLETED"


def test_recovery_requeues_interrupted_curriculum_retired_job(
    db_session,
    monkeypatch,
) -> None:
    """Recovery resets an interrupted curriculum-retired job to SUBMITTED and
    re-runs it, ending COMPLETED with no Coordinator output."""
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
    from server.modules.agents.supervisor import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from server.modules.evaluations.orchestrator import (
        recover_interrupted_evaluation_jobs,
    )
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-recovery-retired@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    _seed_active_prompts(db_session)

    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=slm_id,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.EVALUATING.value,  # stuck, e.g. crashed runner
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
        partial_without_curriculum=True,
        partial_reason="Curriculum evaluation flow retired",
        execution_token=uuid.uuid4(),
        execution_started_at=datetime.now(UTC),
        execution_heartbeat_at=datetime.now(UTC),
    )
    db_session.add(job)
    db_session.commit()

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

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
                    agent_name=agent_name,
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
                    )
                    if agent_name == "sme"
                    else (),
                    summary="ok",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    success=True,
                    prompt_version_id=None,
                )
                for agent_name in ("sme", "gad", "itso")
            ],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor,
        "run_evaluation",
        fake_run_evaluation,
    )

    recovered = recover_interrupted_evaluation_jobs(session_factory)
    assert recovered == 1

    db_session.expire_all()
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.COMPLETED.value
    assert refreshed.error_message is None
    assert "coordinator" not in captured_agents
    assert len(captured_agents) == 3
