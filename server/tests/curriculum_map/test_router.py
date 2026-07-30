"""Router tests using the shared TestClient fixture (server/tests/conftest.py)."""

from __future__ import annotations

import uuid

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.curriculum_map.models import Course
from server.modules.documents.models import Document


def _login(client, db_session, email="faculty@example.com"):
    user = create_user(
        db_session, name="Faculty User", email=email, password="correct-horse-battery",
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


def test_run_check_returns_404_for_unknown_course(client, db_session) -> None:
    user = _login(client, db_session)
    document = Document(
        title="Sample SLM", source_type="slm", file_path="/tmp/x.pdf",
        uploaded_by=user.user_id,
    )
    db_session.add(document)
    db_session.commit()

    response = client.post(
        "/api/v1/curriculum-map/checks",
        json={"document_id": str(document.document_id), "course_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_run_check_returns_422_for_unmapped_course(client, db_session) -> None:
    user = _login(client, db_session)
    course = Course(course_code="IT999", course_title="Unmapped", program="BSIT")
    document = Document(
        title="Sample SLM", source_type="slm", file_path="/tmp/x.pdf",
        uploaded_by=user.user_id,
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
    assert response.status_code == 422


def test_run_check_returns_404_for_non_owner_document(client, db_session) -> None:
    _login(client, db_session)
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    document = Document(
        title="Sample SLM", source_type="slm", file_path="/tmp/x.pdf",
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
