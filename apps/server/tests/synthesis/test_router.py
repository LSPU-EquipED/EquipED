"""HTTP-level monitoring matrix filter regression coverage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from server.modules.auth.models import User, UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.synthesis.models import (
    MonitoringMatrix,
)


def _login(
    client: TestClient, user: User, password: str = "correct-horse-battery"
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert response.status_code == 200

def _add_matrix(db_session, user_id, title: str, program: str) -> None:
    document = Document(
        title=title,
        program=program,
        source_type="slm",
        file_path=f"/tmp/{title}.pdf",
        uploaded_by=user_id,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(MonitoringMatrix(document_id=document.document_id, program=program))


@pytest.fixture()
def matrix_client_data(client, db_session, seeded_user):
    for title, program in (
        ("modern", "BSInfoTech"),
        ("legacy", "BSIT"),
        ("computer science", "BSCS"),
        ("historical", "BSN"),
    ):
        _add_matrix(db_session, seeded_user.user_id, title, program)
    db_session.commit()
    _login(client, seeded_user)
    return client


@pytest.mark.parametrize("program", ["BSInfoTech", "bsit"])
def test_matrix_canonicalizes_bsit_aliases(matrix_client_data, program: str) -> None:
    response = matrix_client_data.get(f"/api/v1/evaluations/matrix?program={program}")
    assert response.status_code == 200
    assert {item["document_title"] for item in response.json()["items"]} == {
        "modern",
        "legacy",
    }


def test_matrix_bscs_filter(matrix_client_data) -> None:
    response = matrix_client_data.get("/api/v1/evaluations/matrix?program=BSCS")
    assert response.status_code == 200
    assert {item["document_title"] for item in response.json()["items"]} == {
        "computer science",
    }


def test_matrix_rejects_unsupported_program(matrix_client_data) -> None:
    response = matrix_client_data.get("/api/v1/evaluations/matrix?program=BSEd")
    assert response.status_code == 422


def test_matrix_preserves_historical_program_rows(matrix_client_data) -> None:
    response = matrix_client_data.get("/api/v1/evaluations/matrix")
    assert response.status_code == 200
    assert "historical" in {item["document_title"] for item in response.json()["items"]}



def test_matrix_route_delegates_to_service(
    client, db_session, seeded_user, monkeypatch
) -> None:
    """The matrix route hands off to the service boundary with query args."""
    from server.modules.synthesis import router as synthesis_router
    from server.modules.synthesis.schemas import MatrixListResponse

    captured: dict = {}

    def fake_get(program, status, page, page_size, db=None):
        captured.update(program=program, status=status, page=page, page_size=page_size)
        return MatrixListResponse(items=[], total=0, page=page, page_size=page_size)

    monkeypatch.setattr(synthesis_router, "service_get_monitoring_matrix", fake_get)
    _login(client, seeded_user)

    response = client.get(
        "/api/v1/evaluations/matrix?program=BSCS&status=COMPLETED&page=2&page_size=10"
    )
    assert response.status_code == 200
    assert captured == {
        "program": "BSCS",
        "status": "COMPLETED",
        "page": 2,
        "page_size": 10,
    }


def test_master_synthesis_detail_success(client, db_session, seeded_user):
    _login(client, seeded_user)

    author = create_user(
        db_session,
        name="Prof. Maria Santos",
        email="maria@lspu.edu.ph",
        password="correct-horse-battery",
        role=UserRole.FACULTY,
    )
    author.department = "College of Computer Studies"
    sme_eval = create_user(
        db_session,
        name="Dr. SME Evaluator",
        email="sme@lspu.edu.ph",
        password="correct-horse-battery",
        role=UserRole.FACULTY,
    )
    sme_eval.department = "Computer Science Department"
    db_session.flush()

    doc = Document(
        document_id=uuid.uuid4(),
        title="Data Structures & Algorithms",
        course_code="COSC 101",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/ds.pdf",
        uploaded_by=author.user_id,
        uploaded_at=datetime.now(UTC),
        processing_status="PROCESSED",
    )
    db_session.add(doc)
    db_session.flush()

    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=doc.document_id,
        target_agent="sme",
        submitted_by=sme_eval.user_id,
        status=EvaluationStatus.COMPLETED.value,
        submitted_at=datetime.now(UTC),
    )
    db_session.add(job)
    db_session.flush()

    matrix = MonitoringMatrix(
        document_id=doc.document_id,
        program="BSCS",
        evaluation_status="COMPLETED",
        synthesized_score=3.65,
        domain_scores_json={
            "sme": {
                "subtotal": 3.8,
                "status": "OK",
                "summary": "Exemplary syllabus alignment",
            },
            "coordinator": {
                "subtotal": 3.5,
                "status": "OK",
                "summary": "Meets institutional competencies",
            },
            "gad": {
                "subtotal": 3.6,
                "status": "OK",
                "summary": "Gender-responsive content throughout",
            },
            "itso": {
                "subtotal": 3.7,
                "status": "OK",
                "summary": "Proper attribution and licensing confirmed",
            },
        },
    )
    db_session.add(matrix)
    db_session.commit()

    response = client.get(f"/api/v1/evaluations/matrix/{doc.document_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == str(doc.document_id)
    assert data["document_title"] == "Data Structures & Algorithms"
    assert data["course_code"] == "COSC 101"
    assert data["program"] == "BSCS"
    assert data["synthesized_score"] == 3.65
    assert data["evaluation_status"] == "COMPLETED"
    assert data["can_certify"] is True

    # Author attribution
    assert data["author"]["name"] == "Prof. Maria Santos"
    assert data["author"]["email"] == "maria@lspu.edu.ph"
    assert data["author"]["department"] == "College of Computer Studies"
    assert data["author"]["user_id"] == str(author.user_id)

    # 4 pillars check
    pillars = data["pillars"]
    assert set(pillars.keys()) == {"sme", "coordinator", "gad", "itso"}
    assert pillars["sme"]["weight"] == 0.35
    assert pillars["sme"]["subtotal"] == 3.8
    assert pillars["sme"]["status"] == "COMPLETED"
    assert pillars["sme"]["summary"] == "Exemplary syllabus alignment"
    assert pillars["sme"]["evaluator"]["name"] == "Dr. SME Evaluator"
    assert pillars["sme"]["evaluator"]["department"] == "Computer Science Department"

    assert pillars["coordinator"]["weight"] == 0.30
    assert pillars["coordinator"]["subtotal"] == 3.5
    assert pillars["coordinator"]["evaluator"] is None

    assert pillars["gad"]["weight"] == 0.20
    assert pillars["gad"]["subtotal"] == 3.6

    assert pillars["itso"]["weight"] == 0.15
    assert pillars["itso"]["subtotal"] == 3.7


def test_master_synthesis_detail_author_null_safe(client, db_session, seeded_user):
    _login(client, seeded_user)

    # Missing user id
    doc_id = uuid.uuid4()
    matrix = MonitoringMatrix(
        document_id=doc_id,
        program="BSCS",
        evaluation_status="IN_PROGRESS",
        domain_scores_json={"sme": {"subtotal": 3.0, "status": "OK"}},
    )
    db_session.add(matrix)
    db_session.commit()

    response = client.get(f"/api/v1/evaluations/matrix/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["author"]["name"] == "Unknown Author"
    assert data["author"]["user_id"] is None
    assert data["can_certify"] is False


def test_master_synthesis_detail_not_found(client, db_session, seeded_user):
    _login(client, seeded_user)
    response = client.get(f"/api/v1/evaluations/matrix/{uuid.uuid4()}")
    assert response.status_code == 404


def test_master_synthesis_detail_admin_only_forbidden_for_faculty(
    client, db_session
):
    faculty = create_user(
        db_session,
        name="Faculty Member",
        email="faculty_test@lspu.edu.ph",
        password="correct-horse-battery",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    _login(client, faculty)

    response = client.get(f"/api/v1/evaluations/matrix/{uuid.uuid4()}")
    assert response.status_code == 403
