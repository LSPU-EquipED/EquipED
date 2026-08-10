"""Criterion feedback endpoint: access control and behavior."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.modules.feedback.models import PreferenceLog
from server.tests.admin.conftest import _auth


def test_criterion_feedback_requires_admin(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin, evaluation_job
):
    url = f"/api/v1/feedback/{evaluation_job.evaluation_id}/criteria/itso-03"
    body = {"agent_name": "itso", "action": "ACCEPT"}

    response = client.post(url, json=body)
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.post(url, json=body)
    assert response.status_code == 403

    _auth(client, auth_cookies_admin)
    response = client.post(url, json=body)
    assert response.status_code == 201


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
