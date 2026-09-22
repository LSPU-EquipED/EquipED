from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk
from server.modules.syllabus_alignment.commands import (
    create_syllabus_alignment,
)
from server.modules.syllabus_alignment.exceptions import SyllabusAlignmentNotFoundError
from server.modules.syllabus_alignment.jobs import (
    fail_interrupted_syllabus_alignments,
    run_syllabus_alignment_job,
)
from server.modules.syllabus_alignment.models import SyllabusAlignmentRun
from server.modules.syllabus_alignment.queries import (
    get_current_syllabus_alignment,
    list_alignment_slms,
)
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
    from server.modules.documents import references as reference_document_service

    monkeypatch.setattr(
        reference_document_service,
        "is_syllabus_reference_ready",
        lambda _document, _db: (True, 2),
    )
    monkeypatch.setattr(
        "server.modules.syllabus_alignment.admission.is_syllabus_reference_ready",
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
    from server.modules.syllabus_alignment import evaluator as syllabus_alignment

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
        "server.modules.syllabus_alignment.admission.is_syllabus_reference_ready",
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
        db_session.query(SyllabusAlignmentRun).filter_by(slm_document_id=slm_id).count()
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
        email="alignment-faculty@lspu.edu.ph",
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
        "server.modules.syllabus_alignment.admission.is_syllabus_reference_ready",
        lambda _document, _db: (True, 2),
    )
    monkeypatch.setattr(
        "server.modules.syllabus_alignment.commands.run_syllabus_alignment_job",
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
    assert (
        listed.json()["items"][0]["current_result"]["alignment_id"]
        == payload["alignment_id"]
    )

    current = client.get(
        "/api/v1/syllabus-alignments/current",
        params={"slm_document_id": str(slm_id)},
    )
    assert current.status_code == 200
    assert current.json()["alignment_id"] == payload["alignment_id"]

    detail = client.get(f"/api/v1/syllabus-alignments/{payload['alignment_id']}")
    assert detail.status_code == 200

    client.post("/api/v1/auth/logout")
    other = create_user(
        db_session,
        name="Other Faculty",
        email="other-alignment@lspu.edu.ph",
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


def test_list_alignment_slms_stats_partition_across_all_states_before_pagination(
    db_session,
):
    """Stats must accurately partition across:
    - no result (pending)
    - QUEUED (pending)
    - RUNNING (pending)
    - MEETS (meets)
    - PARTIALLY_MEETS (partially_meets)
    - DOES_NOT_MEET (needs_attention)
    - FAILED (needs_attention)
    and compute repository-wide totals before pagination."""
    owner = create_user(
        db_session,
        name="Alignment Stats User",
        email="align-stats@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other User",
        email="other-stats@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    syllabus = Document(
        document_id=uuid.uuid4(),
        title="Shared Syllabus",
        source_type="syllabus",
        file_path="/tmp/syllabus.pdf",
        uploaded_by=owner.user_id,
        processing_status="PROCESSED",
    )
    db_session.add(syllabus)
    db_session.commit()

    # Create 7 SLMs for owner
    slms = [
        Document(
            document_id=uuid.uuid4(),
            title=f"SLM Module {i}",
            source_type="slm",
            file_path=f"/tmp/slm_{i}.pdf",
            uploaded_by=owner.user_id,
            uploaded_at=datetime.now(UTC),
            processing_status="PROCESSED",
        )
        for i in range(7)
    ]
    # Create 1 SLM for other user (must not be counted in owner stats)
    other_slm = Document(
        document_id=uuid.uuid4(),
        title="Other SLM",
        source_type="slm",
        file_path="/tmp/other_slm.pdf",
        uploaded_by=other.user_id,
        uploaded_at=datetime.now(UTC),
        processing_status="PROCESSED",
    )
    db_session.add_all(slms + [other_slm])
    db_session.commit()

    # Assign runs:
    # slms[0]: no run -> pending
    # slms[1]: QUEUED -> pending
    # slms[2]: RUNNING -> pending
    # slms[3]: COMPLETED + MEETS -> meets
    # slms[4]: COMPLETED + PARTIALLY_MEETS -> partially_meets
    # slms[5]: COMPLETED + DOES_NOT_MEET -> needs_attention
    # slms[6]: FAILED + UNAVAILABLE -> needs_attention
    runs = [
        SyllabusAlignmentRun(
            slm_document_id=slms[1].document_id,
            syllabus_document_id=syllabus.document_id,
            requested_by=owner.user_id,
            status="QUEUED",
        ),
        SyllabusAlignmentRun(
            slm_document_id=slms[2].document_id,
            syllabus_document_id=syllabus.document_id,
            requested_by=owner.user_id,
            status="RUNNING",
        ),
        SyllabusAlignmentRun(
            slm_document_id=slms[3].document_id,
            syllabus_document_id=syllabus.document_id,
            requested_by=owner.user_id,
            status="COMPLETED",
            alignment_level="MEETS",
        ),
        SyllabusAlignmentRun(
            slm_document_id=slms[4].document_id,
            syllabus_document_id=syllabus.document_id,
            requested_by=owner.user_id,
            status="COMPLETED",
            alignment_level="PARTIALLY_MEETS",
        ),
        SyllabusAlignmentRun(
            slm_document_id=slms[5].document_id,
            syllabus_document_id=syllabus.document_id,
            requested_by=owner.user_id,
            status="COMPLETED",
            alignment_level="DOES_NOT_MEET",
        ),
        SyllabusAlignmentRun(
            slm_document_id=slms[6].document_id,
            syllabus_document_id=syllabus.document_id,
            requested_by=owner.user_id,
            status="FAILED",
            alignment_level="UNAVAILABLE",
        ),
        # Other user's run (must not affect owner's counts)
        SyllabusAlignmentRun(
            slm_document_id=other_slm.document_id,
            syllabus_document_id=syllabus.document_id,
            requested_by=other.user_id,
            status="COMPLETED",
            alignment_level="MEETS",
        ),
    ]
    db_session.add_all(runs)
    db_session.commit()

    # Query page 1 with page_size=2
    resp = list_alignment_slms(
        db_session, requested_by=owner.user_id, page=1, page_size=2
    )
    assert resp.total == 7
    assert len(resp.items) == 2

    stats = resp.stats
    assert stats.total == 7
    assert stats.meets == 1
    assert stats.partially_meets == 1
    assert stats.needs_attention == 2  # DOES_NOT_MEET + FAILED
    assert stats.pending == 3  # no result + QUEUED + RUNNING


def test_list_alignment_slms_search_and_status_filter_and_stats(
    client: TestClient, db_session
):
    owner = create_user(
        db_session,
        name="Search Filter User",
        email="search-filter-slms@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    syllabus = Document(
        document_id=uuid.uuid4(),
        title="Reference Syllabus",
        source_type="syllabus",
        file_path="/tmp/ref_syllabus.pdf",
        uploaded_by=owner.user_id,
        processing_status="PROCESSED",
    )
    db_session.add(syllabus)

    # Create distinct SLMs
    doc1 = Document(
        document_id=uuid.uuid4(),
        title="Python Programming Basics",
        course_title="CS 101 Intro",
        lesson_title="Lesson 1",
        program="BSCS",
        course_code="CS101",
        source_type="slm",
        file_path="/tmp/py.pdf",
        uploaded_by=owner.user_id,
        uploaded_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
        processing_status="PROCESSED",
    )
    doc2 = Document(
        document_id=uuid.uuid4(),
        title="Data Structures in C++",
        course_title="CS 102 Advanced",
        lesson_title="Lesson 2",
        program="BSCS",
        course_code="CS102",
        source_type="slm",
        file_path="/tmp/ds.pdf",
        uploaded_by=owner.user_id,
        uploaded_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC),
        processing_status="PROCESSED",
    )
    doc3 = Document(
        document_id=uuid.uuid4(),
        title="Web Systems and Technologies",
        course_title="IT 201 Web",
        lesson_title="Lesson 3",
        program="BSIT",
        course_code="IT201",
        source_type="slm",
        file_path="/tmp/web.pdf",
        uploaded_by=owner.user_id,
        uploaded_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        processing_status="PROCESSED",
    )
    db_session.add_all([doc1, doc2, doc3])
    db_session.commit()

    # Runs:
    # doc1 -> COMPLETED, MEETS
    # doc2 -> COMPLETED, DOES_NOT_MEET (ATTENTION)
    # doc3 -> none (PENDING)
    run1 = SyllabusAlignmentRun(
        slm_document_id=doc1.document_id,
        syllabus_document_id=syllabus.document_id,
        requested_by=owner.user_id,
        status="COMPLETED",
        alignment_level="MEETS",
    )
    run2 = SyllabusAlignmentRun(
        slm_document_id=doc2.document_id,
        syllabus_document_id=syllabus.document_id,
        requested_by=owner.user_id,
        status="COMPLETED",
        alignment_level="DOES_NOT_MEET",
    )
    db_session.add_all([run1, run2])
    db_session.commit()

    # Test via API router
    client.post(
        "/api/v1/auth/login",
        json={"email": owner.email, "password": "password123"},
    )

    # 1. Search filter: "python"
    res_search = client.get("/api/v1/syllabus-alignments/slms?search=python")
    assert res_search.status_code == 200
    data = res_search.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["document_id"] == str(doc1.document_id)
    # stats must remain repository-wide (total=3, meets=1, attention=1, pending=1)
    assert data["stats"]["total"] == 3
    assert data["stats"]["meets"] == 1
    assert data["stats"]["needs_attention"] == 1
    assert data["stats"]["pending"] == 1

    # 2. Status filter: "MEETS"
    res_status_meets = client.get(
        "/api/v1/syllabus-alignments/slms?status_filter=meets"
    )
    assert res_status_meets.status_code == 200
    data_meets = res_status_meets.json()
    assert data_meets["total"] == 1
    assert data_meets["items"][0]["document_id"] == str(doc1.document_id)
    assert data_meets["stats"]["total"] == 3

    # 3. Status filter: "ATTENTION"
    res_status_att = client.get(
        "/api/v1/syllabus-alignments/slms?status_filter=ATTENTION"
    )
    assert res_status_att.status_code == 200
    data_att = res_status_att.json()
    assert data_att["total"] == 1
    assert data_att["items"][0]["document_id"] == str(doc2.document_id)

    # 4. Status filter: "PENDING"
    res_status_pen = client.get(
        "/api/v1/syllabus-alignments/slms?status_filter=PENDING"
    )
    assert res_status_pen.status_code == 200
    data_pen = res_status_pen.json()
    assert data_pen["total"] == 1
    assert data_pen["items"][0]["document_id"] == str(doc3.document_id)


def test_list_alignment_slms_pagination_deterministic_tie_breaking(db_session):
    owner = create_user(
        db_session,
        name="Determ Alignment User",
        email="determ-align@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    same_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
    id1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
    id2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
    id3 = uuid.UUID("00000000-0000-0000-0000-000000000003")
    id4 = uuid.UUID("00000000-0000-0000-0000-000000000004")

    docs = [
        Document(
            document_id=doc_id,
            title=f"SLM {doc_id}",
            source_type="slm",
            file_path=f"/tmp/{doc_id}.pdf",
            uploaded_by=owner.user_id,
            uploaded_at=same_time,
            processing_status="PROCESSED",
        )
        for doc_id in [id2, id4, id1, id3]
    ]
    db_session.add_all(docs)
    db_session.commit()

    page1 = list_alignment_slms(
        db_session, requested_by=owner.user_id, page=1, page_size=2
    )
    page2 = list_alignment_slms(
        db_session, requested_by=owner.user_id, page=2, page_size=2
    )

    assert [item.document_id for item in page1.items] == [id4, id3]
    assert [item.document_id for item in page2.items] == [id2, id1]
