"""Admin prompt management tests: access control, CRUD, revert."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.admin.models import PromptVersion
from server.tests.admin.conftest import _auth


def test_admin_prompts_get_access_control(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin
) -> None:
    response = client.get("/api/v1/admin/prompts/sme")
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.get("/api/v1/admin/prompts/sme")
    assert response.status_code == 403

    _auth(client, auth_cookies_admin)
    response = client.get("/api/v1/admin/prompts/sme")
    assert response.status_code == 200
    assert response.json() == {"agent_id": "sme", "versions": [], "total": 0}


def test_admin_prompts_post_access_control(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin
) -> None:
    payload = {"prompt_text": "Test prompt", "motivation": "Testing"}

    response = client.post("/api/v1/admin/prompts/sme", json=payload)
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.post("/api/v1/admin/prompts/sme", json=payload)
    assert response.status_code == 403

    _auth(client, auth_cookies_admin)
    response = client.post("/api/v1/admin/prompts/sme", json=payload)
    assert response.status_code == 201


def test_admin_prompts_revert_access_control(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin, db_session
) -> None:
    _auth(client, auth_cookies_admin)
    created = client.post(
        "/api/v1/admin/prompts/sme",
        json={"prompt_text": "Test prompt", "motivation": "Testing"},
    )
    version_id = created.json()["version_id"]
    client.cookies.clear()

    response = client.post(f"/api/v1/admin/prompts/sme/revert/{version_id}")
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.post(f"/api/v1/admin/prompts/sme/revert/{version_id}")
    assert response.status_code == 403

    _auth(client, auth_cookies_admin)
    response = client.post(f"/api/v1/admin/prompts/sme/revert/{version_id}")
    assert response.status_code == 201


def test_admin_preferences_access_control(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin
) -> None:
    response = client.get("/api/v1/admin/preferences")
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.get("/api/v1/admin/preferences")
    assert response.status_code == 403

    _auth(client, auth_cookies_admin)
    response = client.get("/api/v1/admin/preferences")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_create_prompt_version(client: TestClient, auth_cookies_admin, db_session) -> None:
    _auth(client, auth_cookies_admin)
    response = client.post(
        "/api/v1/admin/prompts/sme",
        json={"prompt_text": "Test prompt", "motivation": "Testing"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["version_number"] == 1
    assert body["is_active"] is True
    assert body["prompt_text"] == "Test prompt"

    versions = db_session.query(PromptVersion).filter_by(agent_id="sme").all()
    assert len(versions) == 1
    assert versions[0].is_active is True


def test_create_prompt_deactivates_previous(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _auth(client, auth_cookies_admin)
    first = client.post(
        "/api/v1/admin/prompts/sme",
        json={"prompt_text": "Test prompt 1", "motivation": "Testing 1"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/admin/prompts/sme",
        json={"prompt_text": "Test prompt 2", "motivation": "Testing 2"},
    )
    assert second.status_code == 201
    assert second.json()["version_number"] == 2
    assert second.json()["is_active"] is True

    versions = (
        db_session.query(PromptVersion)
        .filter_by(agent_id="sme")
        .order_by(PromptVersion.version_number)
        .all()
    )
    assert [v.is_active for v in versions] == [False, True]
    assert sum(1 for v in versions if v.is_active) == 1


def test_create_prompt_empty_text_rejected(client: TestClient, auth_cookies_admin) -> None:
    _auth(client, auth_cookies_admin)
    response = client.post("/api/v1/admin/prompts/sme", json={"prompt_text": ""})
    assert response.status_code == 422


def test_create_prompt_unknown_agent(client: TestClient, auth_cookies_admin) -> None:
    _auth(client, auth_cookies_admin)
    response = client.post(
        "/api/v1/admin/prompts/nonexistent",
        json={"prompt_text": "Test prompt", "motivation": "Testing"},
    )
    assert response.status_code == 404


def test_revert_prompt(client: TestClient, auth_cookies_admin, db_session) -> None:
    _auth(client, auth_cookies_admin)
    created = client.post(
        "/api/v1/admin/prompts/sme",
        json={"prompt_text": "Test prompt", "motivation": "Testing"},
    )
    version_1 = created.json()

    reverted = client.post(f"/api/v1/admin/prompts/sme/revert/{version_1['version_id']}")
    assert reverted.status_code == 201

    body = reverted.json()
    assert body["version_number"] == 2
    assert body["prompt_text"] == "Test prompt"
    assert body["is_active"] is True
    assert "Reverted to version 1" in body["motivation"]

    versions = (
        db_session.query(PromptVersion)
        .filter_by(agent_id="sme")
        .order_by(PromptVersion.version_number)
        .all()
    )
    assert [v.is_active for v in versions] == [False, True]


def test_revert_nonexistent_version(client: TestClient, auth_cookies_admin) -> None:
    _auth(client, auth_cookies_admin)
    response = client.post(f"/api/v1/admin/prompts/sme/revert/{uuid4()}")
    assert response.status_code == 404


def test_revert_wrong_agent(client: TestClient, auth_cookies_admin) -> None:
    _auth(client, auth_cookies_admin)
    created = client.post(
        "/api/v1/admin/prompts/sme",
        json={"prompt_text": "Test prompt", "motivation": "Testing"},
    )
    version_id = created.json()["version_id"]

    response = client.post(f"/api/v1/admin/prompts/coordinator/revert/{version_id}")
    assert response.status_code == 404
