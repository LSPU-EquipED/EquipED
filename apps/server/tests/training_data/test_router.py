"""apps/server/tests/training_data/test_router.py"""

from __future__ import annotations

import uuid as uuid_module

from fastapi.testclient import TestClient
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import AgentGeneration, AgentResult
from server.tests.admin.conftest import _auth
from server.tests.evaluations.conftest import _add_document


def _make_gad_generation(db_session, owner_id, agent_id="gad"):
    """See the identical helper's docstring in test_jobs.py (Task 4) for
    why AgentResult must be created first."""
    document_id = _add_document(db_session, owner_id=owner_id, source_type="slm")
    job = EvaluationJob(evaluation_id=uuid_module.uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    agent_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name=agent_id,
        subtotal=2.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="GAD evaluation summary",
        success=True,
    )
    db_session.add(agent_result)
    db_session.flush()

    generation = AgentGeneration(
        generation_id=uuid_module.uuid4(),
        agent_result_id=agent_result.agent_result_id,
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_id=agent_id,
        unit_key="gad-01",
        criterion_ids=["GAD-01"],
        prompt_text="prompt",
        response_text='{"gad-01": {"score": 2, "reasoning": "r"}}',
        response_json={"gad-01": {"score": 2, "reasoning": "r"}},
        response_contract_key="gad_scores.v1",
        response_contract_version=1,
        model_name="test-model",
        envelope_status="ok",
        prompt_sha256="p" * 64,
        response_sha256="r" * 64,
    )
    db_session.add(generation)
    db_session.commit()


def test_start_job_requires_admin(client: TestClient, auth_cookies_faculty):
    _auth(client, auth_cookies_faculty)
    response = client.post("/api/v1/admin/training-data/gad/jobs")
    assert response.status_code == 403


def test_start_job_rejects_unknown_agent(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _auth(client, auth_cookies_admin)
    response = client.post("/api/v1/admin/training-data/not-real/jobs")
    assert response.status_code == 400


def test_start_job_returns_download_and_upload_urls(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    _auth(client, auth_cookies_admin)

    response = client.post("/api/v1/admin/training-data/gad/jobs")

    assert response.status_code == 201
    body = response.json()
    assert body["agent_id"] == "gad"
    assert body["status"] == "pending"
    assert "download_url" in body and "token=" in body["download_url"]
    assert "upload_url" in body and "token=" in body["upload_url"]


def test_download_endpoint_requires_no_login_but_valid_token(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    _auth(client, auth_cookies_admin)
    create_response = client.post("/api/v1/admin/training-data/gad/jobs")
    body = create_response.json()

    client.cookies.clear()  # simulate the anonymous Colab runtime
    download_path = body["download_url"].split("/api/v1", 1)[1]
    download_response = client.get(f"/api/v1{download_path}")

    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/zip"


def test_download_endpoint_rejects_bad_token(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    _auth(client, auth_cookies_admin)
    create_response = client.post("/api/v1/admin/training-data/gad/jobs")
    job_id = create_response.json()["job_id"]

    client.cookies.clear()
    response = client.get(
        f"/api/v1/admin/training-data/jobs/{job_id}/download?token=wrong"
    )
    assert response.status_code == 404


def test_upload_endpoint_stores_adapter_and_list_reflects_it(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path)
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    _auth(client, auth_cookies_admin)
    create_response = client.post("/api/v1/admin/training-data/gad/jobs")
    body = create_response.json()
    job_id = body["job_id"]
    upload_path = body["upload_url"].split("/api/v1", 1)[1]

    client.cookies.clear()
    upload_response = client.post(
        f"/api/v1{upload_path}",
        files={"file": ("adapter.zip", b"fake-bytes", "application/zip")},
    )
    assert upload_response.status_code == 201

    _auth(client, auth_cookies_admin)
    list_response = client.get("/api/v1/admin/training-data/gad/adapters")
    assert list_response.status_code == 200
    adapters = list_response.json()["adapters"]
    assert len(adapters) == 1
    assert adapters[0]["job_id"] == job_id


def test_upload_endpoint_rejects_oversized_file_without_buffering_it(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    tmp_path,
    monkeypatch,
):
    """The router must reject an oversized upload using the client-declared
    Content-Length (via UploadFile.size) before reading the body into
    memory -- not just enforce the cap after fully buffering it."""
    monkeypatch.setattr("server.modules.training_data.adapters.ADAPTER_ROOT", tmp_path)
    monkeypatch.setattr(
        "server.modules.training_data.router.MAX_ADAPTER_UPLOAD_BYTES", 10
    )
    _make_gad_generation(db_session, owner_id=admin_user.user_id)
    _auth(client, auth_cookies_admin)
    create_response = client.post("/api/v1/admin/training-data/gad/jobs")
    body = create_response.json()
    upload_path = body["upload_url"].split("/api/v1", 1)[1]

    client.cookies.clear()
    upload_response = client.post(
        f"/api/v1{upload_path}",
        files={"file": ("adapter.zip", b"x" * 11, "application/zip")},
    )
    assert upload_response.status_code == 422

    _auth(client, auth_cookies_admin)
    list_response = client.get("/api/v1/admin/training-data/gad/adapters")
    assert list_response.json()["adapters"] == []


def test_jobs_list_requires_admin(client: TestClient, auth_cookies_faculty):
    _auth(client, auth_cookies_faculty)
    response = client.get("/api/v1/admin/training-data/gad/jobs")
    assert response.status_code == 403
