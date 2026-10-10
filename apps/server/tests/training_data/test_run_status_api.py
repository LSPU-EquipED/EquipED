"""HTTP tests for run status reporting and its server-observed stages."""

from __future__ import annotations

import io
import json
import uuid
import zipfile

from fastapi.testclient import TestClient
from server.modules.training_data.jobs import create_training_job
from server.modules.training_data.models import DpoTrainingJob
from server.tests.admin.conftest import _auth

from .conftest import make_adapter, seed_eligible_dpo_pair

BASE = "/api/v1/admin/training-data"


def _created(db_session, admin_user):
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    return create_training_job(db_session, "gad", admin_user.user_id)


def _post(client, created, body, token=None):
    token = created.raw_status_token if token is None else token
    return client.post(
        f"{BASE}/jobs/{created.job.job_id}/status?token={token}", json=body
    )


def test_status_post_needs_no_login_but_a_valid_token(
    client: TestClient, db_session, admin_user
):
    created = _created(db_session, admin_user)
    ok = _post(client, created, {"stage": "training", "step": 4, "total": 30})
    assert ok.status_code == 204
    assert (
        _post(client, created, {"stage": "training"}, token="nope").status_code == 404
    )


def test_status_post_rejects_unknown_stage_and_bad_numbers(
    client: TestClient, db_session, admin_user
):
    created = _created(db_session, admin_user)
    for body in (
        {"stage": "exploding"},
        {"stage": "training", "step": -1},
        {"stage": "training", "step": 5, "total": 3},
        {"stage": "training", "total": 0},
        {"stage": "failed", "message": "x" * 501},
    ):
        assert _post(client, created, body).status_code == 422, body


def test_a_token_for_one_job_does_not_work_on_another(
    client: TestClient, db_session, admin_user
):
    first = _created(db_session, admin_user)
    second = create_training_job(db_session, "gad", admin_user.user_id)
    response = client.post(
        f"{BASE}/jobs/{second.job.job_id}/status?token={first.raw_status_token}",
        json={"stage": "training"},
    )
    assert response.status_code == 404


def test_jobs_list_shows_progress_and_age(
    client: TestClient, auth_cookies_admin, db_session, admin_user
):
    created = _created(db_session, admin_user)
    _post(client, created, {"stage": "training", "step": 14, "total": 30})
    _auth(client, auth_cookies_admin)

    item = client.get(f"{BASE}/gad/jobs").json()["jobs"][0]

    assert item["run_stage"] == "training"
    assert (item["run_step"], item["run_total"]) == (14, 30)
    assert 0 <= item["seconds_since_report"] < 60


def test_jobs_list_for_a_job_with_no_report_has_null_progress(
    client: TestClient, auth_cookies_admin, db_session, admin_user
):
    _created(db_session, admin_user)
    _auth(client, auth_cookies_admin)
    item = client.get(f"{BASE}/gad/jobs").json()["jobs"][0]
    assert item["run_stage"] is None
    assert item["seconds_since_report"] is None


def _adapter_zip(manifest: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("adapter_config.json", json.dumps({"base_model_name_or_path": "m"}))
        zf.writestr(
            "training_manifest.json", json.dumps({"source_job_manifest": manifest})
        )
        zf.writestr("adapter_model.safetensors", b"w")
    return buffer.getvalue()


def test_adapter_upload_marks_the_job_converting(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT", tmp_path
    )
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)
    body = client.post(f"{BASE}/gad/jobs").json()
    job = db_session.get(DpoTrainingJob, uuid.UUID(body["job_id"]))
    upload_path = body["upload_url"].split("/api/v1", 1)[1]
    client.cookies.clear()

    response = client.post(
        f"/api/v1{upload_path}",
        files={
            "file": ("adapter.zip", _adapter_zip(job.manifest_json), "application/zip")
        },
    )

    assert response.status_code == 201
    db_session.expire_all()
    assert db_session.get(DpoTrainingJob, job.job_id).run_stage == "converting"


def test_gguf_upload_marks_the_job_finished(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    fake_storage,
    monkeypatch,
):
    monkeypatch.setattr(
        "server.modules.training_data.gguf_files.get_storage_backend",
        lambda: fake_storage,
    )
    adapter = make_adapter(db_session, "sme", 1)
    _auth(client, auth_cookies_admin)

    response = client.post(
        f"{BASE}/sme/adapters/{adapter.adapter_id}/gguf",
        files={"file": ("a.gguf", b"GGUF" + b"x" * 100, "application/octet-stream")},
    )

    assert response.status_code == 201
    db_session.expire_all()
    assert db_session.get(DpoTrainingJob, adapter.job_id).run_stage == "finished"
