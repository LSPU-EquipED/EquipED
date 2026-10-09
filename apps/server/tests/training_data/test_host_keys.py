"""Tests for the host sync key and the read-only host endpoints."""

from __future__ import annotations

import hashlib
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from server.modules.training_data import gguf_files
from server.modules.training_data.models import AgentAdapterPublication
from server.tests.admin.conftest import _auth

from .conftest import make_adapter

BASE = "/api/v1/admin/training-data"
PAYLOAD = b"GGUF" + b"\x02" * 64


@pytest.fixture
def stored(db_session, admin_user, fake_storage, monkeypatch):
    monkeypatch.setattr(
        "server.modules.training_data.gguf_files.get_storage_backend",
        lambda: fake_storage,
    )
    adapter = make_adapter(db_session, "sme", 3)
    gguf_files.store_gguf(
        db_session, adapter, io.BytesIO(PAYLOAD), storage=fake_storage
    )
    return adapter


def _make_key(client, auth_cookies_admin) -> str:
    _auth(client, auth_cookies_admin)
    response = client.post(f"{BASE}/host/key")
    assert response.status_code == 201
    client.cookies.clear()
    return response.json()["key"]


def _hdr(key):
    return {"X-Host-Sync-Key": key}


def test_key_endpoints_require_admin(client: TestClient, auth_cookies_faculty):
    _auth(client, auth_cookies_faculty)
    assert client.post(f"{BASE}/host/key").status_code == 403
    assert client.get(f"{BASE}/host").status_code == 403
    assert client.delete(f"{BASE}/host/key").status_code == 403


def test_create_shows_the_key_once_and_state_never_shows_it(
    client: TestClient, auth_cookies_admin
):
    _auth(client, auth_cookies_admin)
    created = client.post(f"{BASE}/host/key").json()
    assert created["key"].startswith("hsk_")
    state = client.get(f"{BASE}/host").json()
    assert state["has_active_key"] is True
    assert state["last_seen_at"] is None
    assert created["key"] not in str(state)


def test_state_without_a_key(client: TestClient, auth_cookies_admin):
    _auth(client, auth_cookies_admin)
    assert client.get(f"{BASE}/host").json()["has_active_key"] is False


def test_creating_a_new_key_revokes_the_old_one(
    client: TestClient, auth_cookies_admin, stored
):
    old = _make_key(client, auth_cookies_admin)
    new = _make_key(client, auth_cookies_admin)
    assert client.get(f"{BASE}/host/manifest", headers=_hdr(old)).status_code == 404
    assert client.get(f"{BASE}/host/manifest", headers=_hdr(new)).status_code == 200


def test_manifest_lists_stored_ggufs_and_touches_last_seen(
    client: TestClient, auth_cookies_admin, stored, db_session
):
    key = _make_key(client, auth_cookies_admin)

    body = client.get(f"{BASE}/host/manifest", headers=_hdr(key)).json()

    assert body["adapters"] == [
        {
            "adapter_id": str(stored.adapter_id),
            "agent_id": "sme",
            "version": 3,
            "filename": "sme-v3.gguf",
            "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
            "size_bytes": len(PAYLOAD),
            "published": False,
        }
    ]
    _auth(client, auth_cookies_admin)
    assert client.get(f"{BASE}/host").json()["last_seen_at"] is not None


def test_manifest_marks_the_published_version(
    client: TestClient, auth_cookies_admin, admin_user, stored, db_session
):
    db_session.add(
        AgentAdapterPublication(
            agent_id="sme",
            adapter_id=stored.adapter_id,
            published_by=admin_user.user_id,
        )
    )
    db_session.commit()
    key = _make_key(client, auth_cookies_admin)
    body = client.get(f"{BASE}/host/manifest", headers=_hdr(key)).json()
    assert body["adapters"][0]["published"] is True


def test_manifest_skips_adapters_without_a_gguf(
    client: TestClient, auth_cookies_admin, stored, db_session
):
    make_adapter(db_session, "sme", 4)  # no GGUF stored
    key = _make_key(client, auth_cookies_admin)
    body = client.get(f"{BASE}/host/manifest", headers=_hdr(key)).json()
    assert [a["version"] for a in body["adapters"]] == [3]


@pytest.mark.parametrize("headers", [{}, {"X-Host-Sync-Key": "hsk_wrong"}])
def test_host_endpoints_reject_missing_or_wrong_keys_with_404(
    client: TestClient, auth_cookies_admin, stored, headers
):
    _make_key(client, auth_cookies_admin)
    assert client.get(f"{BASE}/host/manifest", headers=headers).status_code == 404
    path = f"{BASE}/host/gguf/{stored.adapter_id}"
    assert client.get(path, headers=headers).status_code == 404


def test_host_download_streams_the_file(client: TestClient, auth_cookies_admin, stored):
    key = _make_key(client, auth_cookies_admin)
    response = client.get(f"{BASE}/host/gguf/{stored.adapter_id}", headers=_hdr(key))
    assert response.status_code == 200
    assert response.content == PAYLOAD
    assert 'filename="sme-v3.gguf"' in response.headers["content-disposition"]


def test_host_download_of_an_unknown_adapter_is_404(
    client: TestClient, auth_cookies_admin
):
    key = _make_key(client, auth_cookies_admin)
    path = f"{BASE}/host/gguf/{uuid.uuid4()}"
    assert client.get(path, headers=_hdr(key)).status_code == 404


def test_revoke_stops_the_key_working(client: TestClient, auth_cookies_admin, stored):
    key = _make_key(client, auth_cookies_admin)
    _auth(client, auth_cookies_admin)
    assert client.delete(f"{BASE}/host/key").status_code == 204
    client.cookies.clear()
    assert client.get(f"{BASE}/host/manifest", headers=_hdr(key)).status_code == 404


def test_host_key_cannot_use_admin_endpoints(
    client: TestClient, auth_cookies_admin, stored
):
    key = _make_key(client, auth_cookies_admin)
    response = client.get(f"{BASE}/sme/adapters", headers=_hdr(key))
    assert response.status_code in (401, 403)
