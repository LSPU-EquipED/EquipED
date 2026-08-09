from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from server.modules.alignment.syllabus.exceptions import SyllabusAlignmentNotFoundError
from server.modules.alignment.syllabus.models import SyllabusAlignmentRun
from server.modules.alignment.syllabus.service import (
    create_syllabus_alignment,
    fail_interrupted_syllabus_alignments,
    get_current_syllabus_alignment,
    run_syllabus_alignment_job,
)
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk
from sqlalchemy.orm import sessionmaker


class CapturedBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, function, *args):
        self.tasks.append((function, args))


def _documents(db_session, owner_id):
    slm_id = uuid.uuid4()
    syllabus_id = uuid.uuid4()
    db_session.add_all(
        [
            Document(
                document_id=slm_id,
                title="Standalone SLM",
                source_type="slm",
                file_path="uploads/slm.pdf",
                uploaded_by=owner_id,
                processing_status="PROCESSED",
            ),
            Document(
                document_id=syllabus_id,
                title="Shared syllabus",
                source_type="syllabus",
                file_path="uploads/syllabus.pdf",
                uploaded_by=owner_id,
                processing_status="PROCESSED",
            ),
            DocumentChunk(
                chunk_id=uuid.uuid4(),
                document_id=slm_id,
                source_type="slm",
                agent_domain="all",
                page_number=1,
                chunk_index=0,
                text="Students configure a secure local area network.",
                chroma_stored=False,
            ),
            DocumentChunk(
                chunk_id=uuid.uuid4(),
                document_id=syllabus_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=2,
                chunk_index=0,
                section_ref="syllabus_course_content:1:1",
                text="Configure secure local area networks.",
                chroma_stored=True,
            ),
        ]
    )
    db_session.commit()
    return slm_id, syllabus_id


def test_standalone_run_persists_without_evaluation_or_agent_result(
    db_session, seeded_user, monkeypatch
):
    slm_id, syllabus_id = _documents(db_session, seeded_user.user_id)
    background = CapturedBackgroundTasks()
    from server.modules.documents.syllabus import (
        service as reference_document_service,
    )

    monkeypatch.setattr(
        reference_document_service,
        "is_syllabus_reference_ready",
        lambda _document, _db: (True, 2),
    )
    # alignment_service imported the function directly.
    monkeypatch.setattr(
        "server.modules.alignment.syllabus.service.is_syllabus_reference_ready",
        lambda _document, _db: (True, 2),
    )

    response = create_syllabus_alignment(
        db_session,
        slm_document_id=slm_id,
        syllabus_document_id=syllabus_id,
        requested_by=seeded_user.user_id,
        background_tasks=background,
    )

    assert response.status == "QUEUED"
    assert response.slm_document_id == slm_id
    assert len(background.tasks) == 1
    row = db_session.get(SyllabusAlignmentRun, response.alignment_id)
    assert row is not None
    assert row.model_name
    assert not hasattr(row, "evaluation_id")
    assert not hasattr(row, "agent_result_id")

    from server.core import database, llm
    from server.modules.alignment.syllabus import evaluator as syllabus_alignment

    session_factory = sessionmaker(bind=db_session.get_bind(), autoflush=False)
    monkeypatch.setattr(database, "get_session_factory", lambda: session_factory)

    class Client:
        model = "sme-test-model"

    captured_syllabus_contents = []

    def evaluate(_client, _chunks, selected_syllabus_id, syllabus_contents):
        captured_syllabus_contents.extend(syllabus_contents)
        return {
            "status": "MEETS",
            "statement": "Every substantial topic is inside the syllabus.",
            "syllabus_document_id": str(selected_syllabus_id),
            "total_topics": 1,
            "aligned_topics": 1,
            "content_matches": [],
            "unmatched_topics": [],
            "advisory_only": True,
        }

    monkeypatch.setattr(llm, "get_llm_client_for_agent", lambda _name: Client())
    monkeypatch.setattr(syllabus_alignment, "evaluate", evaluate)
    task, args = background.tasks[0]
    task(*args)

    db_session.expire_all()
    row = db_session.get(SyllabusAlignmentRun, response.alignment_id)
    assert row.status == "COMPLETED"
    assert row.alignment_level == "MEETS"
    assert row.justification == "Every substantial topic is inside the syllabus."
    assert row.model_name == "sme-test-model"
    assert len(captured_syllabus_contents) == 1
    assert captured_syllabus_contents[0]["content_ref"] == "1:1"
    assert captured_syllabus_contents[0]["content_text"] == (
        "Configure secure local area networks."
    )
    assert captured_syllabus_contents[0]["page_number"] == 2


def test_active_start_is_idempotent_and_terminal_rerun_replaces_result(
    db_session, seeded_user, monkeypatch
):
    slm_id, syllabus_id = _documents(db_session, seeded_user.user_id)
    monkeypatch.setattr(
        "server.modules.alignment.syllabus.service.is_syllabus_reference_ready",
        lambda _document, _db: (True, 1),
    )
    background = CapturedBackgroundTasks()
    first = create_syllabus_alignment(
        db_session,
        slm_document_id=slm_id,
        syllabus_document_id=syllabus_id,
        requested_by=seeded_user.user_id,
        background_tasks=background,
    )
    second = create_syllabus_alignment(
        db_session,
        slm_document_id=slm_id,
        syllabus_document_id=syllabus_id,
        requested_by=seeded_user.user_id,
        background_tasks=background,
    )
    assert second.alignment_id == first.alignment_id
    assert len(background.tasks) == 1

    row = db_session.get(SyllabusAlignmentRun, first.alignment_id)
    replacement_syllabus_id = uuid.uuid4()
    db_session.add(
        Document(
            document_id=replacement_syllabus_id,
            title="Replacement syllabus",
            source_type="syllabus",
            file_path="uploads/replacement-syllabus.pdf",
            uploaded_by=seeded_user.user_id,
            processing_status="PROCESSED",
        )
    )
    row.status = "FAILED"
    row.alignment_level = "UNAVAILABLE"
    row.justification = "Stale justification"
    row.alignment_artifact = {"status": "UNAVAILABLE"}
    row.error_message = "Stale error"
    row.started_at = row.created_at
    row.completed_at = row.created_at
    db_session.commit()
    third = create_syllabus_alignment(
        db_session,
        slm_document_id=slm_id,
        syllabus_document_id=replacement_syllabus_id,
        requested_by=seeded_user.user_id,
        background_tasks=background,
    )
    assert third.alignment_id == first.alignment_id
    assert third.syllabus_document_id == replacement_syllabus_id
    assert third.status == "QUEUED"
    assert third.alignment_level is None
    assert third.justification is None
    assert third.alignment_artifact is None
    assert third.error_message is None
    assert third.started_at is None
    assert third.completed_at is None
    current = get_current_syllabus_alignment(
        db_session,
        slm_document_id=slm_id,
        requested_by=seeded_user.user_id,
    )
    assert current is not None
    assert current.alignment_id == first.alignment_id
    stored_count = (
        db_session.query(SyllabusAlignmentRun)
        .filter_by(slm_document_id=slm_id)
        .count()
    )
    assert stored_count == 1


def test_owner_scope_and_interrupted_recovery(db_session, seeded_user):
    slm_id, syllabus_id = _documents(db_session, seeded_user.user_id)
    other_id = uuid.uuid4()
    with pytest.raises(SyllabusAlignmentNotFoundError):
        get_current_syllabus_alignment(
            db_session,
            slm_document_id=slm_id,
            requested_by=other_id,
        )

    run = SyllabusAlignmentRun(
        slm_document_id=slm_id,
        syllabus_document_id=syllabus_id,
        requested_by=seeded_user.user_id,
        status="RUNNING",
    )
    db_session.add(run)
    db_session.commit()
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False)
    assert fail_interrupted_syllabus_alignments(factory) == 1
    db_session.expire_all()
    recovered = db_session.get(SyllabusAlignmentRun, run.alignment_id)
    assert recovered.status == "FAILED"
    assert recovered.alignment_level == "UNAVAILABLE"


def test_runner_only_claims_a_queued_result(db_session, seeded_user, monkeypatch):
    slm_id, syllabus_id = _documents(db_session, seeded_user.user_id)
    run = SyllabusAlignmentRun(
        slm_document_id=slm_id,
        syllabus_document_id=syllabus_id,
        requested_by=seeded_user.user_id,
        status="RUNNING",
    )
    db_session.add(run)
    db_session.commit()
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False)
    monkeypatch.setattr(
        "server.core.database.get_session_factory",
        lambda: factory,
    )
    monkeypatch.setattr(
        "server.core.llm.get_llm_client_for_agent",
        lambda _name: (_ for _ in ()).throw(
            AssertionError("an already claimed result must not execute again")
        ),
    )

    run_syllabus_alignment_job(run.alignment_id)

    db_session.expire_all()
    assert db_session.get(SyllabusAlignmentRun, run.alignment_id).status == "RUNNING"


def test_standalone_routes_are_owner_scoped_and_do_not_require_evaluation(
    client: TestClient, db_session, seeded_user, monkeypatch
):
    faculty = create_user(
        db_session,
        name="Alignment Faculty",
        email="alignment-faculty@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    slm_id, _unused_syllabus_id = _documents(db_session, faculty.user_id)
    syllabus = Document(
        document_id=uuid.uuid4(),
        title="Admin shared syllabus",
        source_type="syllabus",
        file_path="uploads/admin-syllabus.pdf",
        uploaded_by=seeded_user.user_id,
        processing_status="PROCESSED",
    )
    db_session.add(syllabus)
    db_session.commit()

    monkeypatch.setattr(
        "server.modules.alignment.syllabus.service.is_syllabus_reference_ready",
        lambda _document, _db: (True, 2),
    )
    monkeypatch.setattr(
        "server.modules.alignment.syllabus.service.run_syllabus_alignment_job",
        lambda _alignment_id: None,
    )

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    created = client.post(
        "/api/v1/syllabus-alignments",
        json={
            "slm_document_id": str(slm_id),
            "syllabus_document_id": str(syllabus.document_id),
        },
    )
    assert created.status_code == 202
    payload = created.json()
    assert payload["status"] == "QUEUED"
    assert payload["slm_document_id"] == str(slm_id)

    listed = client.get("/api/v1/syllabus-alignments/slms")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["current_result"]["alignment_id"] == payload[
        "alignment_id"
    ]

    current = client.get(
        "/api/v1/syllabus-alignments/current",
        params={"slm_document_id": str(slm_id)},
    )
    assert current.status_code == 200
    assert current.json()["alignment_id"] == payload["alignment_id"]

    detail = client.get(
        f"/api/v1/syllabus-alignments/{payload['alignment_id']}"
    )
    assert detail.status_code == 200

    client.post("/api/v1/auth/logout")
    other = create_user(
        db_session,
        name="Other Faculty",
        email="other-alignment@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": other.email, "password": "password123"},
    )
    forbidden_detail = client.get(
        f"/api/v1/syllabus-alignments/{payload['alignment_id']}"
    )
    assert forbidden_detail.status_code == 404
