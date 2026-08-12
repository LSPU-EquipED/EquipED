"""HTTP-level monitoring matrix filter regression coverage."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from server.modules.auth.models import User
from server.modules.documents.models import Document
from server.modules.synthesis.models import MonitoringMatrix


def _login(client: TestClient, user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "correct-horse-battery"},
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


def test_results_route_delegates_to_service(
    client, db_session, seeded_user, monkeypatch
) -> None:
    """The results route hands off to the service boundary with user/db args."""
    import uuid as _uuid

    from server.modules.synthesis import router as synthesis_router
    from server.modules.synthesis.schemas import EvaluationResultsResponse

    captured: dict = {}
    eval_id = _uuid.uuid4()

    def fake_get(evaluation_id, current_user_id, db=None):
        captured["evaluation_id"] = evaluation_id
        captured["current_user_id"] = current_user_id
        return EvaluationResultsResponse(
            evaluation_id=evaluation_id,
            document_id=_uuid.uuid4(),
            domain_scores={},
            synthesized_score=0.0,
            active_agents=[],
            failed_agents=[],
            evaluation_status="COMPLETED",
        )

    monkeypatch.setattr(synthesis_router, "service_get_evaluation_results", fake_get)
    _login(client, seeded_user)

    response = client.get(f"/api/v1/evaluations/{eval_id}/results")
    assert response.status_code == 200
    assert captured["evaluation_id"] == eval_id
    assert captured["current_user_id"] == seeded_user.user_id


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
