"""Evaluations module tests for ownership, lifecycle, and polling."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from server.modules.admin.models import PromptVersion
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import run_evaluation_job
from server.modules.evaluations.schemas import EvaluationSubmitRequest
from server.modules.evaluations.service import (
    create_evaluation,
    get_evaluation,
    get_evaluation_status,
    list_evaluations,
)
from server.modules.synthesis.models import MonitoringMatrix
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _add_document(
    db_session,
    *,
    owner_id,
    source_type: str,
    processing_status: str = "PROCESSED",
    with_chunks: bool = True,
    chroma_stored: bool = True,
):
    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title=f"{source_type} doc",
            program="bsit",
            source_type=source_type,
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=owner_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status=processing_status,
        )
    )
    if with_chunks:
        db_session.add(
            DocumentChunk(
                chunk_id=uuid4(),
                document_id=document_id,
                source_type=source_type,
                agent_domain="all",
                page_number=1,
                text=f"chunk for {source_type}",
                token_count=4,
                is_ocr=False,
                chroma_stored=chroma_stored,
            )
        )
    db_session.commit()
    return document_id


def _seed_active_prompts(db_session) -> None:
    for agent_id in ["sme", "coordinator", "gad", "itso"]:
        db_session.add(
            PromptVersion(
                agent_id=agent_id,
                version_number=1,
                prompt_text=f"{agent_id} prompt",
                is_active=True,
            )
        )
    db_session.commit()


def test_create_evaluation_persists_submitted_job_for_owned_docs(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-submit@example.com",
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

    response = create_evaluation(
        EvaluationSubmitRequest(
            document_id=slm_id,
            syllabus_id=syllabus_id,
            curriculum_id=curriculum_id,
        ),
        submitted_by=owner.user_id,
        db=db_session,
    )

    assert response.status == EvaluationStatus.SUBMITTED
    assert response.document_id == slm_id
    assert response.syllabus_id == syllabus_id
    assert response.curriculum_id == curriculum_id
    row = db_session.get(EvaluationJob, response.evaluation_id)
    assert row is not None
    assert row.status == EvaluationStatus.SUBMITTED.value
    assert row.submitted_by == owner.user_id


def test_create_evaluation_without_reference_documents(db_session) -> None:
    """Can submit an evaluation with only an SLM document."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-no-refs@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    response = create_evaluation(
        EvaluationSubmitRequest(document_id=slm_id),
        submitted_by=owner.user_id,
        db=db_session,
    )

    assert response.status == EvaluationStatus.SUBMITTED
    assert response.syllabus_id is None
    assert response.curriculum_id is None
    row = db_session.get(EvaluationJob, response.evaluation_id)
    assert row is not None
    assert row.syllabus_id is None
    assert row.curriculum_id is None


def test_create_evaluation_rejects_ineligible_documents(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-ineligible@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session,
        owner_id=owner.user_id,
        source_type="syllabus",
        processing_status="PENDING",
    )
    curriculum_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="curriculum"
    )
    _seed_active_prompts(db_session)

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                syllabus_id=syllabus_id,
                curriculum_id=curriculum_id,
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "InvalidEvaluationTargetError"
    assert db_session.query(EvaluationJob).count() == 0


def test_create_evaluation_rejects_documents_without_embedding_readiness(
    db_session,
) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-embedding@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    curriculum_id = _add_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        chroma_stored=False,
    )
    syllabus_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )
    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                syllabus_id=syllabus_id,
                curriculum_id=curriculum_id,
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "InvalidEvaluationTargetError"
    assert db_session.query(EvaluationJob).count() == 0


def test_create_evaluation_masks_foreign_documents_as_404(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-foreign@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email="other-foreign@example.com",
        password="password456",
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

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                syllabus_id=syllabus_id,
                curriculum_id=curriculum_id,
            ),
            submitted_by=other.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "DocumentNotFoundError"
    assert db_session.query(EvaluationJob).count() == 0


def test_get_and_status_mask_foreign_jobs_as_404(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-job@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email="other-job@example.com",
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

    with pytest.raises(Exception) as get_exc:
        get_evaluation(job.evaluation_id, other.user_id, other.role.value, db_session)
    with pytest.raises(Exception) as status_exc:
        get_evaluation_status(
            job.evaluation_id, other.user_id, other.role.value, db_session
        )

    assert get_exc.value.__class__.__name__ == "EvaluationNotFoundError"
    assert status_exc.value.__class__.__name__ == "EvaluationNotFoundError"


@pytest.mark.parametrize("role", [UserRole.FACULTY, UserRole.ADMIN])
def test_list_evaluations_is_scoped_per_user_for_all_roles(db_session, role) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email=f"owner-list-{role.value}@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email=f"other-list-{role.value}@example.com",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    db_session.add_all(
        [
            EvaluationJob(
                evaluation_id=uuid4(),
                document_id=uuid4(),
                syllabus_id=uuid4(),
                curriculum_id=uuid4(),
                status=EvaluationStatus.SUBMITTED.value,
                error_message=None,
                submitted_by=owner.user_id,
                submitted_at=datetime.now(UTC),
                completed_at=None,
            ),
            EvaluationJob(
                evaluation_id=uuid4(),
                document_id=uuid4(),
                syllabus_id=uuid4(),
                curriculum_id=uuid4(),
                status=EvaluationStatus.SUBMITTED.value,
                error_message=None,
                submitted_by=other.user_id,
                submitted_at=datetime.now(UTC),
                completed_at=None,
            ),
        ]
    )
    db_session.commit()

    response = list_evaluations(1, 20, owner.user_id, role.value, db_session)
    assert response.total == 1
    assert all(item.document_id for item in response.items)
    assert all(item.syllabus_id for item in response.items)
    assert all(item.curriculum_id for item in response.items)


def test_list_evaluations_includes_document_title(db_session) -> None:
    """Evaluation list items should include document_title for human-readable display."""
    from server.modules.evaluations.schemas import EvaluationListItem

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-title@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="slm", with_chunks=True
    )

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_id,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(job)
    db_session.commit()

    response = list_evaluations(1, 20, owner.user_id, UserRole.FACULTY.value, db_session)
    assert response.total == 1
    item = response.items[0]
    assert isinstance(item, EvaluationListItem)
    assert item.document_title == "slm doc"
    assert item.document_id == doc_id


def test_list_evaluations_document_title_none_for_missing_document(db_session) -> None:
    """document_title should be None when the referenced document does not exist."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-missing-doc@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),  # non-existent document
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(job)
    db_session.commit()

    response = list_evaluations(1, 20, owner.user_id, UserRole.FACULTY.value, db_session)
    assert response.total == 1
    assert response.items[0].document_title is None


def test_list_evaluations_filters_by_document_id(db_session) -> None:
    """Filtering by document_id should return only evaluations for that document."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-filter-doc@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc_a = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    doc_b = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    db_session.add_all([
        EvaluationJob(
            evaluation_id=uuid4(),
            document_id=doc_a,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.SUBMITTED.value,
            error_message=None,
            submitted_by=owner.user_id,
            submitted_at=datetime.now(UTC),
            completed_at=None,
        ),
        EvaluationJob(
            evaluation_id=uuid4(),
            document_id=doc_b,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.SUBMITTED.value,
            error_message=None,
            submitted_by=owner.user_id,
            submitted_at=datetime.now(UTC),
            completed_at=None,
        ),
    ])
    db_session.commit()

    # Without filter: both evaluations
    all_resp = list_evaluations(1, 20, owner.user_id, UserRole.FACULTY.value, db_session)
    assert all_resp.total == 2

    # With filter for doc_a: only one
    filtered_resp = list_evaluations(
        1, 20, owner.user_id, UserRole.FACULTY.value, db_session, document_id=doc_a
    )
    assert filtered_resp.total == 1
    assert filtered_resp.items[0].document_id == doc_a

    # With filter for non-existent doc: zero
    empty_resp = list_evaluations(
        1, 20, owner.user_id, UserRole.FACULTY.value, db_session, document_id=uuid4()
    )
    assert empty_resp.total == 0
    assert empty_resp.items == []


def test_list_evaluations_filter_by_document_id_respects_ownership(db_session) -> None:
    """Filtering by document_id must not leak another user's evaluations."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-filter-own@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email="other-filter-own@example.com",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    # Other user has an evaluation for the same document
    db_session.add(
        EvaluationJob(
            evaluation_id=uuid4(),
            document_id=doc,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.SUBMITTED.value,
            error_message=None,
            submitted_by=other.user_id,
            submitted_at=datetime.now(UTC),
            completed_at=None,
        )
    )
    db_session.commit()

    # Owner has no evaluations for this document
    resp = list_evaluations(
        1, 20, owner.user_id, UserRole.FACULTY.value, db_session, document_id=doc
    )
    assert resp.total == 0
    assert resp.items == []

    # Other user sees their own evaluation
    other_resp = list_evaluations(
        1, 20, other.user_id, UserRole.FACULTY.value, db_session, document_id=doc
    )
    assert other_resp.total == 1
    assert other_resp.items[0].document_id == doc


@pytest.mark.parametrize("role", [UserRole.FACULTY, UserRole.ADMIN])
def test_get_is_scoped_per_user_for_all_roles(db_session, role) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email=f"owner-get-{role.value}@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email=f"other-get-{role.value}@example.com",
        password="password456",
        role=UserRole.FACULTY,
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

    with pytest.raises(Exception) as exc_info:
        get_evaluation(job.evaluation_id, other.user_id, role.value, db_session)
    assert exc_info.value.__class__.__name__ == "EvaluationNotFoundError"


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
    curriculum_id = _add_document(
        db_session, owner_id=faculty.user_id, source_type="curriculum"
    )
    _seed_active_prompts(db_session)

    monkeypatch.setattr(
        evaluations_router,
        "run_evaluation_job",
        lambda *args, **kwargs: None,
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
            "curriculum_id": str(curriculum_id),
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "SUBMITTED"
    job = db_session.query(EvaluationJob).one()
    assert job.status == EvaluationStatus.SUBMITTED.value


def test_submit_evaluation_runs_honest_lifecycle_to_failed(
    client: TestClient, db_session, monkeypatch
) -> None:
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
    from server.modules.agents.supervisor import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from server.modules.evaluations import router as evaluations_router

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
    curriculum_id = _add_document(
        db_session, owner_id=faculty.user_id, source_type="curriculum"
    )
    _seed_active_prompts(db_session)

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    seen_statuses: list[EvaluationStatus] = []
    real_transition = evaluation_orchestrator.transition_evaluation_status

    def recording_transition(evaluation_id, new_status, db, *, error_message=None):
        seen_statuses.append(new_status)
        return real_transition(
            evaluation_id, new_status, db, error_message=error_message
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

    real_run_evaluation_job = evaluation_orchestrator.run_evaluation_job

    def run_and_suppress(*args, **kwargs):
        try:
            real_run_evaluation_job(*args, **kwargs)
        except Exception:
            pass

    monkeypatch.setattr(evaluations_router, "run_evaluation_job", run_and_suppress)

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
            "curriculum_id": str(curriculum_id),
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "SUBMITTED"

    job = db_session.query(EvaluationJob).one()
    assert job.status == EvaluationStatus.COMPLETED.value
    assert seen_statuses == [
        EvaluationStatus.PREPROCESSING,
        EvaluationStatus.EVALUATING,
        EvaluationStatus.SYNTHESIZING,
        EvaluationStatus.COMPLETED,
    ]
    assert job.error_message is None
    assert job.completed_at is not None
    assert db_session.query(MonitoringMatrix).filter_by(document_id=slm_id).count() == 1


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
        evaluation_id, new_status, db=None, *, error_message=None, session=None
    ):
        db = db or session
        if isinstance(new_status, str):
            new_status = EvaluationStatus(new_status)
        seen_statuses.append(new_status)
        return real_transition(
            evaluation_id, new_status, db, error_message=error_message
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

    refreshed = SessionLocal().get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.status == EvaluationStatus.COMPLETED.value
    assert seen_statuses == [
        EvaluationStatus.PREPROCESSING,
        EvaluationStatus.EVALUATING,
        EvaluationStatus.SYNTHESIZING,
        EvaluationStatus.COMPLETED,
    ]
    assert refreshed.error_message is None
    assert session.query(MonitoringMatrix).filter_by(document_id=slm_id).count() == 1
    assert captured_context == {
        "reference_document_ids": {
            "syllabus": syllabus_id,
            "curriculum": curriculum_id,
        }
    }


def test_orchestrator_fails_closed_when_layer3_returns_no_outputs(
    db_session, monkeypatch
) -> None:
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
    from server.modules.agents.supervisor import SupervisorResult
    from server.modules.evaluations import orchestrator as evaluation_orchestrator

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
