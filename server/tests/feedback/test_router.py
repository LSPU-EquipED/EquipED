"""Criterion feedback endpoint: access control and behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient
from server.modules.feedback.models import PreferenceLog
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.tests.admin.conftest import _auth


def test_criterion_feedback_requires_authentication(
    client: TestClient, evaluation_job
):
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"
    body = {"agent_name": "itso", "action": "ACCEPT"}

    response = client.post(url, json=body)
    assert response.status_code == 401


def test_criterion_feedback_admin_allowed_on_any_evaluation(
    client: TestClient, auth_cookies_admin, faculty_evaluation_job
):
    # Admin is not the owner (faculty_evaluation_job belongs to faculty_user)
    # but must still be allowed -- admins can review any evaluation.
    _auth(client, auth_cookies_admin)
    url = f"/api/v1/feedback/{faculty_evaluation_job.evaluation_id}/criteria/itso-03"
    response = client.post(url, json={"agent_name": "itso", "action": "ACCEPT"})
    assert response.status_code == 201


def test_criterion_feedback_owning_faculty_allowed(
    client: TestClient, auth_cookies_faculty, faculty_evaluation_job
):
    _auth(client, auth_cookies_faculty)
    url = f"/api/v1/feedback/{faculty_evaluation_job.evaluation_id}/criteria/itso-03"
    response = client.post(url, json={"agent_name": "itso", "action": "ACCEPT"})
    assert response.status_code == 201


def test_criterion_feedback_non_owning_faculty_masked_as_404(
    client: TestClient, auth_cookies_faculty, evaluation_job
):
    # evaluation_job is owned by admin_user, not faculty_user -- a faculty
    # caller who doesn't own it must be masked as "not found", not 403, so
    # they can't use this endpoint to probe which evaluation IDs exist.
    _auth(client, auth_cookies_faculty)
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"
    response = client.post(url, json={"agent_name": "itso", "action": "ACCEPT"})
    assert response.status_code == 404


def test_criterion_feedback_edit_requires_score_and_justification(
    client: TestClient, auth_cookies_admin, evaluation_job
):
    _auth(client, auth_cookies_admin)
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"

    response = client.post(url, json={"agent_name": "itso", "action": "EDIT"})
    assert response.status_code == 422

    response = client.post(
        url,
        json={
            "agent_name": "itso",
            "action": "EDIT",
            "score": 2,
            "justification": "Reviewer correction: no bibliography section found.",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["agent_name"] == "itso"
    assert body["criterion_id"] == "itso-03"
    assert body["action"] == "EDIT"
    assert body["edited_json"] == {
        "score": 2,
        "justification": "Reviewer correction: no bibliography section found.",
    }


def test_criterion_feedback_unknown_evaluation_returns_404(
    client: TestClient, auth_cookies_admin
):
    _auth(client, auth_cookies_admin)
    import uuid

    url = f"/api/v1/feedback/{uuid.uuid4()}/criteria/itso-03"
    response = client.post(url, json={"agent_name": "itso", "action": "ACCEPT"})
    assert response.status_code == 404


def test_criterion_feedback_persists_row(
    client: TestClient, auth_cookies_admin, evaluation_job, admin_user, db_session
):
    _auth(client, auth_cookies_admin)
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"
    client.post(url, json={"agent_name": "itso", "action": "REJECT", "notes": "wrong"})

    rows = db_session.query(PreferenceLog).all()
    assert len(rows) == 1
    assert rows[0].agent_name == "itso"
    assert rows[0].criterion_id == "itso-03"
    assert rows[0].action == "REJECT"
    assert rows[0].notes == "wrong"
    assert rows[0].user_id == admin_user.user_id


def test_criterion_feedback_accepts_sme_agent_name(
    client: TestClient, auth_cookies_admin, evaluation_job
):
    _auth(client, auth_cookies_admin)
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/A-01"
    response = client.post(url, json={"agent_name": "sme", "action": "ACCEPT"})
    assert response.status_code == 201
    assert response.json()["agent_name"] == "sme"


def test_criterion_feedback_valid_sme_and_itso(
    client: TestClient, auth_cookies_admin, evaluation_job
):
    _auth(client, auth_cookies_admin)
    # Valid ITSO
    url_itso = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"
    res_itso = client.post(url_itso, json={"agent_name": "itso", "action": "ACCEPT"})
    assert res_itso.status_code == 201
    assert res_itso.json()["agent_name"] == "itso"
    assert res_itso.json()["criterion_id"] == "itso-03"

    # Valid SME
    url_sme = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/A-01"
    res_sme = client.post(url_sme, json={"agent_name": "sme", "action": "ACCEPT"})
    assert res_sme.status_code == 201
    assert res_sme.json()["agent_name"] == "sme"
    assert res_sme.json()["criterion_id"] == "A-01"


def test_criterion_feedback_valid_coordinator_and_gad(
    client: TestClient, auth_cookies_admin, evaluation_job
):
    _auth(client, auth_cookies_admin)
    # Valid Coordinator
    url_coord = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/OP-01"
    res_coord = client.post(
        url_coord, json={"agent_name": "coordinator", "action": "ACCEPT"}
    )
    assert res_coord.status_code == 201
    assert res_coord.json()["agent_name"] == "coordinator"
    assert res_coord.json()["criterion_id"] == "OP-01"

    # Valid GAD
    url_gad = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/GAD-01"
    res_gad = client.post(url_gad, json={"agent_name": "gad", "action": "ACCEPT"})
    assert res_gad.status_code == 201
    assert res_gad.json()["agent_name"] == "gad"
    assert res_gad.json()["criterion_id"] == "GAD-01"


def test_criterion_feedback_valid_all_four_agents(
    client: TestClient, auth_cookies_admin, evaluation_job
):
    _auth(client, auth_cookies_admin)
    cases = [
        ("itso-03", "itso"),
        ("A-01", "sme"),
        ("OP-01", "coordinator"),
        ("GAD-01", "gad"),
    ]
    for criterion_id, agent_name in cases:
        url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/{criterion_id}"
        response = client.post(url, json={"agent_name": agent_name, "action": "ACCEPT"})
        assert response.status_code == 201
        assert response.json()["agent_name"] == agent_name
        assert response.json()["criterion_id"] == criterion_id


def test_criterion_feedback_unknown_criterion_returns_422(
    client: TestClient, auth_cookies_admin, evaluation_job
):
    _auth(client, auth_cookies_admin)
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/unknown-crit"
    response = client.post(url, json={"agent_name": "itso", "action": "ACCEPT"})
    assert response.status_code == 422


def test_criterion_feedback_wrong_agent_returns_422(
    client: TestClient, auth_cookies_admin, evaluation_job
):
    _auth(client, auth_cookies_admin)
    # A-01 belongs to SME, not ITSO
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/A-01"
    response = client.post(url, json={"agent_name": "itso", "action": "ACCEPT"})
    assert response.status_code == 422


def test_criterion_feedback_wrong_document_or_result_returns_422(
    client: TestClient, auth_cookies_admin, evaluation_job, db_session
):
    _auth(client, auth_cookies_admin)
    from uuid import uuid4

    # CriterionScore with mismatched document_id
    mismatched_doc_id = uuid4()
    agent_result = (
        db_session.query(AgentResult)
        .filter(
            AgentResult.evaluation_id == evaluation_job.evaluation_id,
            AgentResult.agent_name == "itso",
        )
        .first()
    )
    score_mismatched = CriterionScore(
        agent_result_id=agent_result.agent_result_id,
        evaluation_id=evaluation_job.evaluation_id,
        document_id=mismatched_doc_id,
        criterion_id="itso-mismatched",
        criterion_title="Mismatched Doc",
        score=3,
        justification="Mismatched document ID",
    )
    db_session.add(score_mismatched)
    db_session.commit()

    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-mismatched"
    response = client.post(url, json={"agent_name": "itso", "action": "ACCEPT"})
    assert response.status_code == 422


def test_criterion_feedback_ambiguous_target_returns_422(
    client: TestClient, auth_cookies_admin, evaluation_job, db_session
):
    _auth(client, auth_cookies_admin)
    agent_result = (
        db_session.query(AgentResult)
        .filter(
            AgentResult.evaluation_id == evaluation_job.evaluation_id,
            AgentResult.agent_name == "itso",
        )
        .first()
    )
    # Add duplicate CriterionScore for itso-03
    duplicate_score = CriterionScore(
        agent_result_id=agent_result.agent_result_id,
        evaluation_id=evaluation_job.evaluation_id,
        document_id=evaluation_job.document_id,
        criterion_id="itso-03",
        criterion_title="References / Bibliography Duplicate",
        score=2,
        justification="Duplicate entry",
    )
    db_session.add(duplicate_score)
    db_session.commit()

    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"
    response = client.post(url, json={"agent_name": "itso", "action": "ACCEPT"})
    assert response.status_code == 422


def test_criterion_feedback_justification_max_length_boundary(
    client: TestClient, auth_cookies_admin, evaluation_job
):
    _auth(client, auth_cookies_admin)
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"

    # Exactly 2000 characters -> Accepted (201)
    justification_2000 = "x" * 2000
    res_2000 = client.post(
        url,
        json={
            "agent_name": "itso",
            "action": "EDIT",
            "score": 3,
            "justification": justification_2000,
        },
    )
    assert res_2000.status_code == 201
    assert res_2000.json()["edited_json"]["justification"] == justification_2000

    # 2001 characters -> Rejected via Pydantic/FastAPI validation (422)
    justification_2001 = "x" * 2001
    res_2001 = client.post(
        url,
        json={
            "agent_name": "itso",
            "action": "EDIT",
            "score": 3,
            "justification": justification_2001,
        },
    )
    assert res_2001.status_code == 422
