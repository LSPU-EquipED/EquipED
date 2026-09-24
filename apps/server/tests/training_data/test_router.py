"""apps/server/tests/training_data/test_router.py"""

from __future__ import annotations

import io
import json
import uuid
import zipfile

from fastapi.testclient import TestClient
from server.tests.admin.conftest import _auth
from server.tests.training_data.conftest import seed_eligible_dpo_pair


def _make_adapter_zip(
    source_manifest: dict,
    *,
    weights_filename: str = "adapter_model.safetensors",
    weights_content: bytes = b"lora-weights",
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "adapter_config.json", json.dumps({"base_model_name_or_path": "model"})
        )
        zf.writestr(
            "training_manifest.json",
            json.dumps({"source_job_manifest": source_manifest}),
        )
        zf.writestr(weights_filename, weights_content)
    return buffer.getvalue()


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


def test_start_job_rejects_empty_dataset(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _auth(client, auth_cookies_admin)
    # gad has 0 pairs
    response = client.post("/api/v1/admin/training-data/gad/jobs")
    assert response.status_code == 422
    assert "no eligible DPO preference pairs exist" in response.json()["detail"]


def test_start_job_returns_download_and_upload_urls(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
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
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
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
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
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
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)
    create_response = client.post("/api/v1/admin/training-data/gad/jobs")
    body = create_response.json()
    job_id = uuid.UUID(body["job_id"])
    upload_path = body["upload_url"].split("/api/v1", 1)[1]

    # Inspect job manifest to create valid matching archive
    from server.modules.training_data.models import DpoTrainingJob

    job_record = db_session.get(DpoTrainingJob, job_id)
    zip_bytes = _make_adapter_zip(job_record.manifest_json)

    client.cookies.clear()
    upload_response = client.post(
        f"/api/v1{upload_path}",
        files={"file": ("adapter.zip", zip_bytes, "application/zip")},
    )
    assert upload_response.status_code == 201

    _auth(client, auth_cookies_admin)
    list_response = client.get("/api/v1/admin/training-data/gad/adapters")
    assert list_response.status_code == 200
    adapters = list_response.json()["adapters"]
    assert len(adapters) == 1
    assert adapters[0]["job_id"] == str(job_id)


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
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        "server.modules.training_data.router.MAX_ADAPTER_UPLOAD_BYTES", 10
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
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


def test_jobs_list_includes_frozen_manifest_summary(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)
    created = client.post("/api/v1/admin/training-data/gad/jobs").json()

    response = client.get("/api/v1/admin/training-data/gad/jobs")

    assert response.status_code == 200
    (job,) = response.json()["jobs"]
    assert job["job_id"] == created["job_id"]
    assert job["pair_count"] == 1
    assert job["evaluation_count"] == 1
    assert isinstance(job["reviewer_count"], int)
    assert len(job["pairs_sha256"]) == 64
    assert job["export_timestamp"]


def test_jobs_list_tolerates_sparse_manifest(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    from server.modules.training_data.models import DpoTrainingJob

    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)
    created = client.post("/api/v1/admin/training-data/gad/jobs").json()
    job = db_session.get(DpoTrainingJob, uuid.UUID(created["job_id"]))
    job.manifest_json = {}
    db_session.commit()

    response = client.get("/api/v1/admin/training-data/gad/jobs")

    assert response.status_code == 200
    (item,) = response.json()["jobs"]
    assert item["pair_count"] is None
    assert item["evaluation_count"] is None
    assert item["reviewer_count"] is None
    assert item["pairs_sha256"] is None
    assert item["export_timestamp"] is None


def test_readiness_requires_admin(client: TestClient, auth_cookies_faculty):
    _auth(client, auth_cookies_faculty)
    response = client.get("/api/v1/admin/training-data/gad/readiness")
    assert response.status_code == 403


def test_readiness_rejects_unknown_agent(
    client: TestClient, auth_cookies_admin, admin_user
):
    _auth(client, auth_cookies_admin)
    response = client.get("/api/v1/admin/training-data/not-real/readiness")
    assert response.status_code == 400


def test_readiness_reports_zero_pairs_without_error(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    _auth(client, auth_cookies_admin)

    response = client.get("/api/v1/admin/training-data/gad/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == "gad"
    assert body["pair_count"] == 0
    assert body["evaluation_count"] == 0
    assert body["reviewer_count"] == 0


def test_readiness_matches_what_a_job_would_freeze_and_creates_nothing(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)

    readiness = client.get("/api/v1/admin/training-data/gad/readiness").json()

    assert client.get("/api/v1/admin/training-data/gad/jobs").json()["jobs"] == []
    assert readiness["pair_count"] == 1
    assert readiness["evaluation_count"] == 1
    assert isinstance(readiness["skipped_counts"], dict)
    assert readiness["export_timestamp"]

    client.post("/api/v1/admin/training-data/gad/jobs")
    (job,) = client.get("/api/v1/admin/training-data/gad/jobs").json()["jobs"]
    assert job["pairs_sha256"] == readiness["pairs_sha256"]
    assert job["pair_count"] == readiness["pair_count"]
