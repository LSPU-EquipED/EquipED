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


def test_start_job_urls_use_public_base_url_when_configured(
    client: TestClient, auth_cookies_admin, admin_user, db_session, monkeypatch
):
    from server.core.config import get_settings

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://abc.trycloudflare.com/")
    get_settings.cache_clear()
    try:
        seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
        _auth(client, auth_cookies_admin)

        body = client.post("/api/v1/admin/training-data/gad/jobs").json()

        job_id = body["job_id"]
        assert body["download_url"].startswith(
            f"https://abc.trycloudflare.com/api/v1/admin/training-data/jobs/{job_id}/"
        )
        assert body["upload_url"].startswith(
            f"https://abc.trycloudflare.com/api/v1/admin/training-data/jobs/{job_id}/"
        )
        assert "token=" in body["download_url"] and "token=" in body["upload_url"]
    finally:
        get_settings.cache_clear()


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


def _fake_state(monkeypatch, *, reachable=True, loaded=()):
    from server.modules.training_data.serving import LoadedAdapter, ServerAdapterState

    state = ServerAdapterState(
        reachable,
        tuple(LoadedAdapter(i, a, v) for i, (a, v) in enumerate(loaded)),
        tuple(range(len(loaded))),
        (),
    )
    monkeypatch.setattr(
        "server.modules.training_data.router.get_server_adapter_state",
        lambda: state,
    )


def test_list_adapters_includes_loaded_and_published(
    client: TestClient, db_session, admin_user, auth_cookies_admin, monkeypatch
):
    from server.tests.training_data.conftest import make_adapter

    v1 = make_adapter(db_session, "sme", 1)
    make_adapter(db_session, "sme", 2)
    _fake_state(monkeypatch, loaded=[("sme", 1)])
    _auth(client, auth_cookies_admin)
    put = client.put(
        "/api/v1/admin/training-data/sme/published",
        json={"adapter_id": str(v1.adapter_id)},
    )
    assert put.status_code == 200
    body = client.get("/api/v1/admin/training-data/sme/adapters").json()
    by_version = {a["version"]: a for a in body["adapters"]}
    assert by_version[1]["loaded"] is True and by_version[1]["published"] is True
    assert by_version[1]["gguf_filename"] == "sme-v1.gguf"
    assert by_version[2]["loaded"] is False and by_version[2]["published"] is False
    assert body["published_adapter_id"] == str(v1.adapter_id)
    assert body["server_reachable"] is True


def test_list_adapters_returns_training_summary(
    client: TestClient, db_session, admin_user, auth_cookies_admin, monkeypatch
):
    from server.tests.training_data.conftest import make_adapter

    v1 = make_adapter(db_session, "sme", 1)
    make_adapter(db_session, "sme", 2)
    v1.training_summary = {
        "version": 1,
        "steps": 12,
        "last": {"step": 12, "margin": 1.4, "accuracy": 1.0},
    }
    db_session.commit()
    _fake_state(monkeypatch, loaded=[])
    _auth(client, auth_cookies_admin)

    body = client.get("/api/v1/admin/training-data/sme/adapters").json()
    by_version = {a["version"]: a for a in body["adapters"]}
    assert by_version[1]["training_summary"]["last"]["margin"] == 1.4
    assert by_version[1]["training_summary"]["steps"] == 12
    assert by_version[2]["training_summary"] is None


def test_publish_requires_loaded_adapter(
    client: TestClient, db_session, admin_user, auth_cookies_admin, monkeypatch
):
    from server.tests.training_data.conftest import make_adapter

    v1 = make_adapter(db_session, "sme", 1)
    _auth(client, auth_cookies_admin)
    url = "/api/v1/admin/training-data/sme/published"
    payload = {"adapter_id": str(v1.adapter_id)}

    _fake_state(monkeypatch, loaded=[])  # reachable, not loaded
    assert client.put(url, json=payload).status_code == 409

    _fake_state(monkeypatch, reachable=False)  # unreachable
    assert client.put(url, json=payload).status_code == 409

    body = client.get("/api/v1/admin/training-data/sme/adapters").json()
    assert body["published_adapter_id"] is None
    assert body["server_reachable"] is False
    assert body["adapters"][0]["loaded"] is None


def test_publish_mismatched_agent_is_422_and_unknown_is_404(
    client: TestClient, db_session, admin_user, auth_cookies_admin, monkeypatch
):
    from server.tests.training_data.conftest import make_adapter

    gad1 = make_adapter(db_session, "gad", 1)
    _fake_state(monkeypatch, loaded=[("gad", 1)])
    _auth(client, auth_cookies_admin)
    url = "/api/v1/admin/training-data/sme/published"

    wrong = client.put(url, json={"adapter_id": str(gad1.adapter_id)})
    assert wrong.status_code == 422
    unknown = client.put(url, json={"adapter_id": str(uuid.uuid4())})
    assert unknown.status_code == 404


def test_publish_and_unpublish_require_admin(
    client: TestClient, db_session, admin_user, auth_cookies_faculty
):
    from server.tests.training_data.conftest import make_adapter

    v1 = make_adapter(db_session, "sme", 1)
    _auth(client, auth_cookies_faculty)
    url = "/api/v1/admin/training-data/sme/published"
    assert client.put(url, json={"adapter_id": str(v1.adapter_id)}).status_code == 403
    assert client.delete(url).status_code == 403


def test_unpublish_returns_204_and_clears(
    client: TestClient, db_session, admin_user, auth_cookies_admin, monkeypatch
):
    from server.tests.training_data.conftest import make_adapter

    v1 = make_adapter(db_session, "sme", 1)
    _fake_state(monkeypatch, loaded=[("sme", 1)])
    _auth(client, auth_cookies_admin)
    url = "/api/v1/admin/training-data/sme/published"
    assert client.put(url, json={"adapter_id": str(v1.adapter_id)}).status_code == 200

    assert client.delete(url).status_code == 204
    body = client.get("/api/v1/admin/training-data/sme/adapters").json()
    assert body["published_adapter_id"] is None
    assert body["adapters"][0]["published"] is False


# --------------------------- GGUF endpoints ---------------------------------

_BASE = "/api/v1/admin/training-data"
_GOOD = b"GGUF" + b"x" * 100


def _patch_storage(monkeypatch, fake_storage):
    monkeypatch.setattr(
        "server.modules.training_data.gguf_files.get_storage_backend",
        lambda: fake_storage,
    )


def _patch_adapter_root(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "server.modules.training_data.adapter_artifacts.ADAPTER_ROOT", tmp_path
    )


def _zip_upload(client, auth_cookies_admin, admin_user, db_session):
    """Run job -> zip upload; return the upload response json."""
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)
    body = client.post(f"{_BASE}/gad/jobs").json()
    from server.modules.training_data.models import DpoTrainingJob

    job = db_session.get(DpoTrainingJob, uuid.UUID(body["job_id"]))
    zip_bytes = _make_adapter_zip(job.manifest_json)
    upload_path = body["upload_url"].split("/api/v1", 1)[1]
    client.cookies.clear()
    resp = client.post(
        f"/api/v1{upload_path}",
        files={"file": ("adapter.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 201
    return resp.json()


def _gguf_path(url: str) -> str:
    return "/api/v1" + url.split("/api/v1", 1)[1]


def test_zip_upload_returns_gguf_upload_url(
    client,
    auth_cookies_admin,
    admin_user,
    db_session,
    tmp_path,
    monkeypatch,
    fake_storage,
):
    _patch_adapter_root(monkeypatch, tmp_path)
    _patch_storage(monkeypatch, fake_storage)
    data = _zip_upload(client, auth_cookies_admin, admin_user, db_session)
    assert data["gguf"] is None
    assert (
        f"/admin/training-data/adapters/{data['adapter_id']}/gguf?token="
        in data["gguf_upload_url"]
    )


def test_zip_upload_survives_gguf_token_failure(
    client, auth_cookies_admin, admin_user, db_session, tmp_path, monkeypatch
):
    _patch_adapter_root(monkeypatch, tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(
        "server.modules.training_data.router.issue_gguf_upload_token", boom
    )
    data = _zip_upload(client, auth_cookies_admin, admin_user, db_session)
    assert data["gguf_upload_url"] is None


def test_token_upload_stores_gguf_once(
    client,
    auth_cookies_admin,
    admin_user,
    db_session,
    tmp_path,
    monkeypatch,
    fake_storage,
):
    import hashlib

    _patch_adapter_root(monkeypatch, tmp_path)
    _patch_storage(monkeypatch, fake_storage)
    data = _zip_upload(client, auth_cookies_admin, admin_user, db_session)
    path = _gguf_path(data["gguf_upload_url"])
    files = {"file": ("a.gguf", _GOOD, "application/octet-stream")}

    r = client.post(path, files=files)
    assert r.status_code == 201
    assert r.json()["gguf"]["size_bytes"] == len(_GOOD)
    assert len(fake_storage.objects) == 1

    again = client.post(path, files=files)
    assert again.status_code == 404
    assert again.json()["detail"] == "not found"

    _auth(client, auth_cookies_admin)
    items = client.get(f"{_BASE}/gad/adapters").json()["adapters"]
    assert items[0]["gguf"]["sha256"] == hashlib.sha256(_GOOD).hexdigest()


def test_token_upload_bad_magic_keeps_token_valid(
    client,
    auth_cookies_admin,
    admin_user,
    db_session,
    tmp_path,
    monkeypatch,
    fake_storage,
):
    _patch_adapter_root(monkeypatch, tmp_path)
    _patch_storage(monkeypatch, fake_storage)
    data = _zip_upload(client, auth_cookies_admin, admin_user, db_session)
    path = _gguf_path(data["gguf_upload_url"])
    bad = client.post(path, files={"file": ("a.gguf", b"NOPE" + b"x" * 50, "x/y")})
    assert bad.status_code == 422
    assert fake_storage.objects == {}
    ok = client.post(path, files={"file": ("a.gguf", _GOOD, "x/y")})
    assert ok.status_code == 201


def test_token_upload_rejects_non_gguf_filename(
    client,
    auth_cookies_admin,
    admin_user,
    db_session,
    tmp_path,
    monkeypatch,
    fake_storage,
):
    _patch_adapter_root(monkeypatch, tmp_path)
    _patch_storage(monkeypatch, fake_storage)
    data = _zip_upload(client, auth_cookies_admin, admin_user, db_session)
    path = _gguf_path(data["gguf_upload_url"])
    r = client.post(path, files={"file": ("a.bin", _GOOD, "x/y")})
    assert r.status_code == 422
    assert fake_storage.objects == {}


def test_token_upload_wrong_expired_or_other_adapter(
    client,
    auth_cookies_admin,
    admin_user,
    db_session,
    tmp_path,
    monkeypatch,
    fake_storage,
):
    from datetime import UTC, datetime, timedelta

    from server.modules.training_data.models import TrainedAdapter
    from server.tests.training_data.conftest import make_adapter

    _patch_adapter_root(monkeypatch, tmp_path)
    _patch_storage(monkeypatch, fake_storage)
    data = _zip_upload(client, auth_cookies_admin, admin_user, db_session)
    path = _gguf_path(data["gguf_upload_url"])
    token = path.split("token=")[1]
    files = {"file": ("a.gguf", _GOOD, "x/y")}

    wrong = client.post(path.split("token=")[0] + "token=wrong", files=files)
    assert wrong.status_code == 404 and wrong.json()["detail"] == "not found"

    other = make_adapter(db_session, "sme", 1)
    foreign = client.post(
        f"{_BASE}/adapters/{other.adapter_id}/gguf?token={token}", files=files
    )
    assert foreign.status_code == 404 and foreign.json()["detail"] == "not found"

    unknown = client.post(
        f"{_BASE}/adapters/{uuid.uuid4()}/gguf?token={token}", files=files
    )
    assert unknown.status_code == 404

    adapter = db_session.get(TrainedAdapter, uuid.UUID(data["adapter_id"]))
    adapter.gguf_upload_expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()
    expired = client.post(path, files=files)
    assert expired.status_code == 404 and expired.json()["detail"] == "not found"
    assert fake_storage.objects == {}


def test_admin_upload_conflict_replace_and_auth(
    client,
    db_session,
    admin_user,
    auth_cookies_admin,
    auth_cookies_faculty,
    monkeypatch,
    fake_storage,
):
    from server.tests.training_data.conftest import make_adapter

    _patch_storage(monkeypatch, fake_storage)
    v1 = make_adapter(db_session, "sme", 1)
    url = f"{_BASE}/sme/adapters/{v1.adapter_id}/gguf"
    files = {"file": ("a.gguf", _GOOD, "x/y")}

    client.cookies.clear()
    assert client.post(url, files=files).status_code in (401, 403)
    _auth(client, auth_cookies_faculty)
    assert client.post(url, files=files).status_code == 403

    client.cookies.clear()
    _auth(client, auth_cookies_admin)
    assert client.post(url, files=files).status_code == 201
    assert client.post(url, files=files).status_code == 409
    assert client.post(url + "?replace=true", files=files).status_code == 201
    bad_name = client.post(
        url + "?replace=true", files={"file": ("a.txt", _GOOD, "x/y")}
    )
    assert bad_name.status_code == 422


def test_gguf_routes_enforce_agent_ownership(
    client, db_session, admin_user, auth_cookies_admin, monkeypatch, fake_storage
):
    from server.tests.training_data.conftest import make_adapter

    _patch_storage(monkeypatch, fake_storage)
    sme = make_adapter(db_session, "sme", 1)
    _auth(client, auth_cookies_admin)
    base = f"{_BASE}/gad/adapters/{sme.adapter_id}/gguf"
    files = {"file": ("a.gguf", _GOOD, "x/y")}
    assert client.post(base, files=files).status_code == 404
    assert client.post(base + "/download-link", json={}).status_code == 404
    assert client.get(base + "/file").status_code == 404
    assert client.delete(base).status_code == 404
    assert fake_storage.objects == {}


def test_gguf_download_link(
    client, db_session, admin_user, auth_cookies_admin, monkeypatch, fake_storage
):
    from datetime import UTC, datetime, timedelta

    from server.tests.training_data.conftest import make_adapter

    _patch_storage(monkeypatch, fake_storage)
    v1 = make_adapter(db_session, "sme", 1)
    _auth(client, auth_cookies_admin)
    base = f"{_BASE}/sme/adapters/{v1.adapter_id}/gguf"

    assert client.post(base + "/download-link", json={}).status_code == 404

    client.post(base, files={"file": ("a.gguf", _GOOD, "x/y")})
    r = client.post(base + "/download-link", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["url"].startswith("https://r2.example/")
    assert body["filename"] == "sme-v1.gguf"
    assert body["size_bytes"] == len(_GOOD)
    assert len(body["sha256"]) == 64
    expires = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    delta = expires - datetime.now(UTC)
    assert timedelta(hours=23) < delta <= timedelta(hours=24, minutes=1)
    assert fake_storage.presigned[-1][1] == 24 * 3600

    for hours in (0, 169):
        bad = client.post(base + "/download-link", json={"expires_in_hours": hours})
        assert bad.status_code == 422

    fake_storage.presign_result = None
    fallback = client.post(base + "/download-link", json={}).json()
    assert fallback["url"].endswith(
        f"/admin/training-data/sme/adapters/{v1.adapter_id}/gguf/file"
    )


def test_gguf_file_streams_with_attachment_header(
    client, db_session, admin_user, auth_cookies_admin, monkeypatch, fake_storage
):
    from server.tests.training_data.conftest import make_adapter

    _patch_storage(monkeypatch, fake_storage)
    v1 = make_adapter(db_session, "sme", 1)
    _auth(client, auth_cookies_admin)
    base = f"{_BASE}/sme/adapters/{v1.adapter_id}/gguf"

    assert client.get(base + "/file").status_code == 404
    client.post(base, files={"file": ("a.gguf", _GOOD, "x/y")})
    r = client.get(base + "/file")
    assert r.status_code == 200
    assert r.content == _GOOD
    assert r.headers["content-type"] == "application/octet-stream"
    assert r.headers["content-disposition"] == 'attachment; filename="sme-v1.gguf"'


def test_gguf_delete(
    client, db_session, admin_user, auth_cookies_admin, monkeypatch, fake_storage
):
    from server.tests.training_data.conftest import make_adapter

    _patch_storage(monkeypatch, fake_storage)
    v1 = make_adapter(db_session, "sme", 1)
    v2 = make_adapter(db_session, "sme", 2)
    _fake_state(monkeypatch, loaded=[("sme", 1)])
    _auth(client, auth_cookies_admin)
    b1 = f"{_BASE}/sme/adapters/{v1.adapter_id}/gguf"
    b2 = f"{_BASE}/sme/adapters/{v2.adapter_id}/gguf"
    files = {"file": ("a.gguf", _GOOD, "x/y")}

    assert client.delete(b2).status_code == 404
    client.post(b1, files=files)
    client.post(b2, files=files)
    client.put(f"{_BASE}/sme/published", json={"adapter_id": str(v1.adapter_id)})

    assert client.delete(b1).status_code == 409
    assert client.delete(b2).status_code == 204
    items = client.get(f"{_BASE}/sme/adapters").json()["adapters"]
    by_version = {a["version"]: a for a in items}
    assert by_version[2]["gguf"] is None
    assert by_version[1]["gguf"] is not None


# ------------------- fix wave: missing storage object, fallback -------------


def test_gguf_link_and_file_404_when_object_missing(
    client, db_session, admin_user, auth_cookies_admin, monkeypatch, fake_storage
):
    from server.tests.training_data.conftest import make_adapter

    _patch_storage(monkeypatch, fake_storage)
    v1 = make_adapter(db_session, "sme", 1)
    _auth(client, auth_cookies_admin)
    base = f"{_BASE}/sme/adapters/{v1.adapter_id}/gguf"
    client.post(base, files={"file": ("a.gguf", _GOOD, "x/y")})
    fake_storage.objects.clear()
    assert client.post(base + "/download-link", json={}).status_code == 404
    assert client.get(base + "/file").status_code == 404


def test_zip_upload_survives_token_and_rollback_failure(
    client, auth_cookies_admin, admin_user, db_session, tmp_path, monkeypatch
):
    _patch_adapter_root(monkeypatch, tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(
        "server.modules.training_data.router.issue_gguf_upload_token", boom
    )
    from sqlalchemy.orm import Session

    real_rollback = Session.rollback

    def dead_rollback(self):
        raise ConnectionError("dead")

    monkeypatch.setattr(Session, "rollback", dead_rollback)
    try:
        data = _zip_upload(client, auth_cookies_admin, admin_user, db_session)
    finally:
        monkeypatch.setattr(Session, "rollback", real_rollback)
    assert data["gguf_upload_url"] is None
    assert data["adapter_id"]


def test_zip_upload_survives_dead_connection_after_token_failure(
    client, auth_cookies_admin, admin_user, db_session, tmp_path, monkeypatch
):
    """Even re-reading the adapter after the failure must not 500 the upload."""
    _patch_adapter_root(monkeypatch, tmp_path)

    def boom(session, adapter):
        session.expire_all()  # attribute reads now need the (dead) connection
        raise RuntimeError("nope")

    monkeypatch.setattr(
        "server.modules.training_data.router.issue_gguf_upload_token", boom
    )
    from sqlalchemy.orm import Session

    real_refresh = Session.refresh

    def dead_refresh(self, *a, **k):
        raise ConnectionError("dead")

    monkeypatch.setattr(Session, "refresh", dead_refresh)
    try:
        data = _zip_upload(client, auth_cookies_admin, admin_user, db_session)
    finally:
        monkeypatch.setattr(Session, "refresh", real_refresh)
    assert data["gguf_upload_url"] is None


def test_start_job_returns_a_filled_notebook(
    client: TestClient, auth_cookies_admin, admin_user, db_session
):
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)

    body = client.post("/api/v1/admin/training-data/gad/jobs").json()

    notebook = json.loads(body["notebook"])
    cell = "".join(notebook["cells"][1]["source"])
    assert body["download_url"] in cell
    assert body["upload_url"] in cell
    assert "PASTE_DOWNLOAD_URL_HERE" not in cell
    assert "PASTE_UPLOAD_URL_HERE" not in cell
    assert body["notebook_filename"] == (
        f"equiped-gad-run-{body['job_id'][:8]}.ipynb"
    )


def test_start_job_still_succeeds_when_the_notebook_cannot_be_built(
    client: TestClient, auth_cookies_admin, admin_user, db_session, monkeypatch
):
    from server.modules.training_data.exceptions import NotebookTemplateError

    def boom(*args, **kwargs):
        raise NotebookTemplateError("broken template")

    monkeypatch.setattr("server.modules.training_data.router.build_job_notebook", boom)
    seed_eligible_dpo_pair(db_session, owner_id=admin_user.user_id, agent_id="gad")
    _auth(client, auth_cookies_admin)

    response = client.post("/api/v1/admin/training-data/gad/jobs")

    assert response.status_code == 201
    body = response.json()
    assert body["notebook"] is None
    assert body["notebook_filename"] is None
    assert "token=" in body["download_url"]
