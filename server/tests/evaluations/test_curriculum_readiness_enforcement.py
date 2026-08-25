"""Tests for curriculum readiness enforcement during evaluation orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.sme.rubric import REGISTERED_CODES
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.exceptions import EvaluationPipelineFailure
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import _execute_claimed_evaluation
from server.modules.evaluations.service import acquire_evaluation_execution
from server.modules.synthesis.models import MonitoringMatrix


def _create_test_environment(
    db_session,
    *,
    curriculum_uploader_role: UserRole = UserRole.ADMIN,
    curriculum_status: str = "PROCESSED",
    curriculum_program: str = "BSCS",
    job_program: str = "BSCS",
    partial: bool = False,
    with_curriculum_chunks: bool = True,
):
    admin = create_user(
        db_session,
        name="Admin User",
        email=f"admin-{uuid4()}@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    uploader = admin
    if curriculum_uploader_role != UserRole.ADMIN:
        uploader = create_user(
            db_session,
            name="Faculty Uploader",
            email=f"faculty-{uuid4()}@example.com",
            password="password123",
            role=curriculum_uploader_role,
        )
    faculty_user = create_user(
        db_session,
        name="Faculty Submitter",
        email=f"submitter-{uuid4()}@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = uuid4()
    db_session.add(
        Document(
            document_id=slm_id,
            title="SLM Document",
            program=job_program,
            source_type="slm",
            file_path=f"uploads/{slm_id}.pdf",
            uploaded_by=faculty_user.user_id,
            processing_status="PROCESSED",
            page_count=1,
            has_ocr_pages=False,
        )
    )
    db_session.add(
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=slm_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="slm content for evaluation",
            token_count=5,
            is_ocr=False,
            chroma_stored=False,
        )
    )

    curriculum_id = None
    if not partial:
        curriculum_id = uuid4()
        db_session.add(
            Document(
                document_id=curriculum_id,
                title="Curriculum Document",
                program=curriculum_program,
                source_type="curriculum",
                file_path=f"uploads/{curriculum_id}.pdf",
                uploaded_by=uploader.user_id,
                processing_status=curriculum_status,
                page_count=1,
                has_ocr_pages=False,
            )
        )
        if with_curriculum_chunks:
            db_session.add(
                DocumentChunk(
                    chunk_id=uuid4(),
                    document_id=curriculum_id,
                    source_type="curriculum",
                    agent_domain="all",
                    page_number=1,
                    text="curriculum text content",
                    token_count=4,
                    is_ocr=False,
                    chroma_stored=True,
                )
            )

    job_id = uuid4()
    job = EvaluationJob(
        evaluation_id=job_id,
        document_id=slm_id,
        curriculum_id=curriculum_id,
        status=EvaluationStatus.SUBMITTED.value,
        submitted_by=faculty_user.user_id,
        submitted_at=datetime.now(UTC),
        confirmed_program=job_program,
        partial_without_curriculum=partial,
        partial_reason="Deliberate partial" if partial else None,
    )
    db_session.add(job)
    db_session.commit()
    return job_id


def _mock_successful_supervisor(
    monkeypatch, evaluation_id, document_id, *, partial=False
):
    agents = ["sme", "gad", "itso"]
    if not partial:
        agents.append("coordinator")
    agent_results = [
        AgentEvaluationResult(
            agent_name=agent,
            evaluation_id=evaluation_id,
            document_id=document_id,
            subtotal=3.0,
            criterion_scores=tuple(
                CriterionScore(code, f"{code} title", 3, "good evidence", ())
                for code in sorted(REGISTERED_CODES)
            )
            if agent == "sme"
            else (
                (CriterionScore("A-05", "A-05 title", 3, "good evidence", ()),)
                if agent == "coordinator"
                else ()
            ),
            summary="ok",
            model_name=f"{agent}-model",
            processing_seconds=0.1,
            token_count=10,
            success=True,
            error_message=None,
        )
        for agent in agents
    ]

    class FakeSupervisor:
        def __init__(self, *args, **kwargs):
            pass

        def run_evaluation(self, **kwargs):
            return SimpleNamespace(agent_results=list(agent_results))

    monkeypatch.setattr(
        "server.modules.evaluations.orchestrator.Supervisor", FakeSupervisor
    )


def _claim_and_execute(db_session, evaluation_id):
    token = uuid4()
    assert acquire_evaluation_execution(db_session, evaluation_id, token)
    db_session.commit()
    try:
        _execute_claimed_evaluation(
            evaluation_id, execution_token=token, db_session_factory=lambda: db_session
        )
    except EvaluationPipelineFailure:
        pass
    db_session.expire_all()


def test_full_evaluation_stale_curriculum_status_fails(db_session, monkeypatch):
    """Curriculum with non-PROCESSED status must fail full evaluation honestly."""
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: True,
    )
    job_id = _create_test_environment(
        db_session, curriculum_status="PENDING", partial=False
    )
    job = db_session.get(EvaluationJob, job_id)
    _mock_successful_supervisor(monkeypatch, job_id, job.document_id, partial=False)

    _claim_and_execute(db_session, job_id)

    refreshed_job = db_session.get(EvaluationJob, job_id)
    assert refreshed_job.status == EvaluationStatus.FAILED.value
    matrix = db_session.query(MonitoringMatrix).filter_by(evaluation_id=job_id).first()
    assert matrix is not None
    assert matrix.evaluation_status == "FAILED"


def test_full_evaluation_non_admin_provenance_fails(db_session, monkeypatch):
    """Curriculum uploaded by a non-admin must fail full evaluation honestly."""
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: True,
    )
    job_id = _create_test_environment(
        db_session,
        curriculum_uploader_role=UserRole.FACULTY,
        partial=False,
    )
    job = db_session.get(EvaluationJob, job_id)
    _mock_successful_supervisor(monkeypatch, job_id, job.document_id, partial=False)

    _claim_and_execute(db_session, job_id)

    refreshed_job = db_session.get(EvaluationJob, job_id)
    assert refreshed_job.status == EvaluationStatus.FAILED.value
    matrix = db_session.query(MonitoringMatrix).filter_by(evaluation_id=job_id).first()
    assert matrix is not None
    assert matrix.evaluation_status == "FAILED"


def test_full_evaluation_missing_vectors_fails(db_session, monkeypatch):
    """Curriculum with missing Chroma vectors must fail full evaluation honestly."""
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: False,
    )
    job_id = _create_test_environment(db_session, partial=False)
    job = db_session.get(EvaluationJob, job_id)
    _mock_successful_supervisor(monkeypatch, job_id, job.document_id, partial=False)

    _claim_and_execute(db_session, job_id)

    refreshed_job = db_session.get(EvaluationJob, job_id)
    assert refreshed_job.status == EvaluationStatus.FAILED.value
    matrix = db_session.query(MonitoringMatrix).filter_by(evaluation_id=job_id).first()
    assert matrix is not None
    assert matrix.evaluation_status == "FAILED"


def test_full_evaluation_final_readiness_drift_fails(db_session, monkeypatch):
    """Status/provenance/vector drift before final synthesis must yield FAILED."""
    chroma_available_state = True

    def dynamic_chroma_check(doc_id, source_type):
        return chroma_available_state

    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        dynamic_chroma_check,
    )
    job_id = _create_test_environment(db_session, partial=False)
    job = db_session.get(EvaluationJob, job_id)

    agents = ["sme", "gad", "itso", "coordinator"]
    agent_results = [
        AgentEvaluationResult(
            agent_name=agent,
            evaluation_id=job_id,
            document_id=job.document_id,
            subtotal=3.0,
            criterion_scores=tuple(
                CriterionScore(code, f"{code} title", 3, "good evidence", ())
                for code in sorted(REGISTERED_CODES)
            )
            if agent == "sme"
            else (),
            summary="ok",
            model_name=f"{agent}-model",
            processing_seconds=0.1,
            token_count=10,
            success=True,
            error_message=None,
        )
        for agent in agents
    ]

    class FakeSupervisorWithDrift:
        def __init__(self, *args, **kwargs):
            pass

        def run_evaluation(self, **kwargs):
            nonlocal chroma_available_state
            # Simulate vector drift occurring during / after agent execution
            chroma_available_state = False
            return SimpleNamespace(agent_results=list(agent_results))

    monkeypatch.setattr(
        "server.modules.evaluations.orchestrator.Supervisor",
        FakeSupervisorWithDrift,
    )

    _claim_and_execute(db_session, job_id)

    refreshed_job = db_session.get(EvaluationJob, job_id)
    assert refreshed_job.status == EvaluationStatus.FAILED.value
    assert "curriculum" in (refreshed_job.error_message or "").lower()
    matrix = db_session.query(MonitoringMatrix).filter_by(evaluation_id=job_id).first()
    assert matrix is not None
    assert matrix.evaluation_status == "FAILED"
    assert matrix.evaluation_status != "COMPLETED"
    assert matrix.evaluation_status != "COMPLETED_PARTIAL"


def test_successful_full_evaluation_behavior_unchanged(db_session, monkeypatch):
    """Valid full evaluation with ready curriculum completes as COMPLETED."""
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: True,
    )
    job_id = _create_test_environment(db_session, partial=False)
    job = db_session.get(EvaluationJob, job_id)
    _mock_successful_supervisor(monkeypatch, job_id, job.document_id, partial=False)

    _claim_and_execute(db_session, job_id)

    refreshed_job = db_session.get(EvaluationJob, job_id)
    assert refreshed_job.status == EvaluationStatus.COMPLETED.value
    assert refreshed_job.partial_without_curriculum is False
    assert refreshed_job.error_message is None
    matrix = db_session.query(MonitoringMatrix).filter_by(evaluation_id=job_id).first()
    assert matrix is not None
    assert matrix.evaluation_status == "COMPLETED"


def test_successful_partial_evaluation_without_curriculum_unchanged(
    db_session, monkeypatch
):
    """Deliberate partial without curriculum completes as COMPLETED_PARTIAL."""
    job_id = _create_test_environment(db_session, partial=True)
    job = db_session.get(EvaluationJob, job_id)
    _mock_successful_supervisor(monkeypatch, job_id, job.document_id, partial=True)

    _claim_and_execute(db_session, job_id)

    refreshed_job = db_session.get(EvaluationJob, job_id)
    assert refreshed_job.status == EvaluationStatus.COMPLETED.value
    assert refreshed_job.partial_without_curriculum is True
    matrix = db_session.query(MonitoringMatrix).filter_by(evaluation_id=job_id).first()
    assert matrix is not None
    assert matrix.evaluation_status == "COMPLETED_PARTIAL"
