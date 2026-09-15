"""Admin preference log view: agent_name/criterion_id surfacing."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.service import create_criterion_feedback
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.tests.admin.conftest import _auth
from server.tests.evaluations.conftest import _add_document


def test_admin_preferences_include_agent_and_criterion(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    document_id = _add_document(
        db_session, owner_id=admin_user.user_id, source_type="slm"
    )
    job = EvaluationJob(evaluation_id=uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    agent_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name="itso",
        subtotal=3.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="ITSO evaluation summary",
        success=True,
    )
    db_session.add(agent_result)
    db_session.flush()

    score = CriterionScore(
        agent_result_id=agent_result.agent_result_id,
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        criterion_id="itso-03",
        criterion_title="References / Bibliography",
        score=3,
        justification="Adequate references provided.",
    )
    db_session.add(score)
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
