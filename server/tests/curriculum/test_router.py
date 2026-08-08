"""Router tests using the shared TestClient fixture (server/tests/conftest.py)."""

from __future__ import annotations

import threading
import uuid
from dataclasses import replace
from datetime import UTC, datetime

from server.modules.alignment import curriculum as alignment_curriculum
from server.modules.alignment.curriculum.models import CurriculumAlignmentCheck
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.curriculum.models import Course
from server.modules.documents.models import Document


def _login(client, db_session, email="faculty@example.com"):
    user = create_user(
        db_session,
        name="Faculty User",
        email=email,
        password="correct-horse-battery",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "correct-horse-battery"}
    )
    assert response.status_code == 200
    return user


def test_list_courses_requires_auth(client) -> None:
    response = client.get("/api/v1/curriculum-map/courses")
    assert response.status_code == 401


def test_list_courses_returns_seeded_courses(client, db_session) -> None:
    _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    db_session.add(course)
    db_session.commit()

    response = client.get("/api/v1/curriculum-map/courses")
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["course_code"] == "IT301"


def test_run_check_returns_409_for_unprocessed_document(client, db_session) -> None:
    """An unprocessed SLM must fail the gate with 409, not reach the LLM."""
    user = _login(client, db_session)
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/x.pdf",
        uploaded_by=user.user_id,
        processing_status="PENDING",
    )
    db_session.add(document)
    db_session.commit()

    response = client.post(
        "/api/v1/curriculum-map/checks",
        json={"document_id": str(document.document_id), "course_id": str(uuid.uuid4())},
    )
    assert response.status_code == 409


def test_run_check_returns_404_for_unknown_course(
    client, db_session, monkeypatch
) -> None:
    """Unknown course id returns 404 once the document gate has passed."""
    from server.modules.alignment.curriculum import service as service_module

    user = _login(client, db_session)
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/x.pdf",
        uploaded_by=user.user_id,
        processing_status="PROCESSED",
        program="BSInfoTech",
    )
    db_session.add(document)
    db_session.commit()

    def _empty_pages(_db, _document_id):
        return []

    monkeypatch.setattr(service_module, "load_document_pages", _empty_pages)

    response = client.post(
        "/api/v1/curriculum-map/checks",
        json={"document_id": str(document.document_id), "course_id": str(uuid.uuid4())},
    )
    assert response.status_code == 409


def test_run_check_returns_422_for_unmapped_course(
    client, db_session, monkeypatch
) -> None:
    """A BSIT course with no mapped objectives is 422 once the document gate
    has passed and the document has usable persisted text."""
    from server.modules.alignment.curriculum import service as service_module

    user = _login(client, db_session)
    course = Course(course_code="IT999", course_title="Unmapped", program="BSIT")
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/x.pdf",
        uploaded_by=user.user_id,
        processing_status="PROCESSED",
        program="BSInfoTech",
    )
    db_session.add_all([course, document])
    db_session.commit()

    fake_page = service_module.DocumentPage(page_number=1, text="sample slm text")
    monkeypatch.setattr(
        service_module, "load_document_pages", lambda _db, _document_id: [fake_page]
    )

    response = client.post(
        "/api/v1/curriculum-map/checks",
        json={
            "document_id": str(document.document_id),
            "course_id": str(course.course_id),
        },
    )
    assert response.status_code == 422


def test_run_check_returns_429_for_duplicate_request_within_cooldown(
    client, db_session
) -> None:
    user = _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/x.pdf",
        uploaded_by=user.user_id,
        processing_status="PROCESSED",
        program="BSInfoTech",
    )
    db_session.add_all([course, document])
    db_session.commit()

    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={
            "total_mapped_objectives": 0,
            "match": 0,
            "under_developed": 0,
            "over_developed": 0,
            "not_addressed": 0,
        },
        success=True,
        run_at=datetime.now(UTC),
    )
    db_session.add(check)
    db_session.commit()

    response = client.post(
        "/api/v1/curriculum-map/checks",
        json={
            "document_id": str(document.document_id),
            "course_id": str(course.course_id),
        },
    )

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1


def test_run_check_returns_429_when_slot_is_saturated(
    client, db_session, monkeypatch
) -> None:
    user = _login(client, db_session)
    course = Course(
        course_code="IT301",
        course_title="Data Structures",
        program="BSInfoTech",
    )
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/sample.pdf",
        uploaded_by=user.user_id,
        processing_status="PROCESSED",
        program="BSInfoTech",
    )
    db_session.add_all([course, document])
    db_session.commit()

    base_settings = replace(
        alignment_curriculum.router.get_settings(),
        curriculum_alignment_max_concurrent_checks=1,
        curriculum_alignment_max_checks_per_user=1,
    )
    previous_override = client.app.dependency_overrides.pop(
        alignment_curriculum.router.get_settings,
        None,
    )
    client.app.dependency_overrides[
        alignment_curriculum.router.get_settings
    ] = lambda: base_settings

    started = threading.Event()
    release = threading.Event()

    def _slow_run(**_: object) -> CurriculumAlignmentCheck:
        started.set()
        release.wait(1.0)
        return CurriculumAlignmentCheck(
            check_id=uuid.uuid4(),
            document_id=document.document_id,
            course_id=course.course_id,
            objective_results=[],
            summary={
                "total_mapped_objectives": 0,
                "match": 0,
                "under_developed": 0,
                "over_developed": 0,
                "not_addressed": 0,
            },
            success=True,
            run_at=datetime.now(UTC),
            model_name="fake",
        )

    monkeypatch.setattr(
        alignment_curriculum.router, "run_curriculum_alignment_check", _slow_run
    )

    def _first() -> None:
        client.post(
            "/api/v1/curriculum-map/checks",
            json={
                "document_id": str(document.document_id),
                "course_id": str(course.course_id),
            },
        )

    first = threading.Thread(target=_first)
    first.start()
    assert started.wait(1.0)

    try:
        second = client.post(
            "/api/v1/curriculum-map/checks",
            json={
                "document_id": str(document.document_id),
                "course_id": str(course.course_id),
            },
        )
        assert second.status_code == 429
        assert int(second.headers["Retry-After"]) >= 1
    finally:
        release.set()
        first.join()
        if previous_override is None:
            client.app.dependency_overrides.pop(
                alignment_curriculum.router.get_settings, None
            )
        else:
            client.app.dependency_overrides[
                alignment_curriculum.router.get_settings
            ] = previous_override


def test_run_check_returns_404_for_non_owner_document(client, db_session) -> None:
    _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/x.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add_all([course, document])
    db_session.commit()

    response = client.post(
        "/api/v1/curriculum-map/checks",
        json={
            "document_id": str(document.document_id),
            "course_id": str(course.course_id),
        },
    )
    assert response.status_code == 404


def test_get_check_returns_404_for_unknown_id(client, db_session) -> None:
    _login(client, db_session)
    response = client.get(f"/api/v1/curriculum-map/checks/{uuid.uuid4()}")
    assert response.status_code == 404


def test_list_checks_requires_auth(client) -> None:
    response = client.get("/api/v1/curriculum-map/checks")
    assert response.status_code == 401


def test_list_checks_returns_only_current_users_checks(client, db_session) -> None:
    user = _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/x.pdf",
        uploaded_by=user.user_id,
    )
    db_session.add_all([course, document])
    db_session.commit()

    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={
            "total_mapped_objectives": 0,
            "match": 0,
            "under_developed": 0,
            "over_developed": 0,
            "not_addressed": 0,
        },
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    response = client.get("/api/v1/curriculum-map/checks")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["items"][0]["check_id"] == str(check.check_id)
    assert body["items"][0]["document_title"] == "Sample SLM"
    assert body["items"][0]["course_title"] == "Data Structures"


def test_list_checks_returns_empty_items_for_new_user(client, db_session) -> None:
    _login(client, db_session)
    response = client.get("/api/v1/curriculum-map/checks")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_delete_check_returns_404_for_unknown_id(client, db_session) -> None:
    _login(client, db_session)
    response = client.delete(f"/api/v1/curriculum-map/checks/{uuid.uuid4()}")
    assert response.status_code == 404


def test_delete_check_returns_404_for_non_owner_check(client, db_session) -> None:
    _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    other_owner_document = Document(
        title="Not mine",
        source_type="slm",
        file_path="/tmp/x.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add_all([course, other_owner_document])
    db_session.commit()
    check = CurriculumAlignmentCheck(
        document_id=other_owner_document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={
            "total_mapped_objectives": 0,
            "match": 0,
            "under_developed": 0,
            "over_developed": 0,
            "not_addressed": 0,
        },
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    response = client.delete(f"/api/v1/curriculum-map/checks/{check.check_id}")
    assert response.status_code == 404


def test_delete_check_succeeds_for_owner(client, db_session) -> None:
    user = _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/x.pdf",
        uploaded_by=user.user_id,
    )
    db_session.add_all([course, document])
    db_session.commit()
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={
            "total_mapped_objectives": 0,
            "match": 0,
            "under_developed": 0,
            "over_developed": 0,
            "not_addressed": 0,
        },
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    response = client.delete(f"/api/v1/curriculum-map/checks/{check.check_id}")
    assert response.status_code == 204
    assert db_session.get(CurriculumAlignmentCheck, check.check_id) is None
