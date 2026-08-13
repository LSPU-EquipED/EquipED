"""Admin preference log view: agent_name/criterion_id surfacing."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from server.modules.feedback.service import create_criterion_feedback
from server.tests.admin.conftest import _auth
from server.tests.evaluations.conftest import _add_document


def test_admin_preferences_include_agent_and_criterion(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    from server.modules.evaluations.models import EvaluationJob
    from uuid import uuid4

    document_id = _add_document(db_session, owner_id=admin_user.user_id, source_type="slm")
    job = EvaluationJob(evaluation_id=uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.commit()

    create_criterion_feedback(
        db_session,
        evaluation_id=job.evaluation_id,
        criterion_id="itso-03",
        agent_name="itso",
        action="ACCEPT",
        user_id=admin_user.user_id,
        user_role="admin",
    )

    _auth(client, auth_cookies_admin)
    response = client.get("/api/v1/admin/preferences")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["agent_name"] == "itso"
    assert items[0]["criterion_id"] == "itso-03"
