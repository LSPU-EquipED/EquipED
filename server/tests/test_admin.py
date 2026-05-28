"""Admin module tests for access control and prompt management."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.admin.models import PromptVersion
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user


def _auth(client: TestClient, cookies: dict[str, str] | None) -> None:
    if cookies:
        client.cookies.update(cookies)


@pytest.fixture()
def admin_user(db_session):
    user = create_user(
        db_session,
        name="Admin User",
        email="admin@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return user


@pytest.fixture()
def faculty_user(db_session):
    user = create_user(
        db_session,
        name="Faculty User",
        email="faculty@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    return user


@pytest.fixture()
def auth_cookies_admin(client: TestClient, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "password123"},
    )
    cookies = dict(response.cookies)
    client.cookies.clear()
    return cookies


@pytest.fixture()
def auth_cookies_faculty(client: TestClient, faculty_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": faculty_user.email, "password": "password123"},
    )
    cookies = dict(response.cookies)
    client.cookies.clear()
    return cookies


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


# ---------------------------------------------------------------------------
# User management endpoint tests
# ---------------------------------------------------------------------------

def test_admin_list_users_requires_admin(client: TestClient, auth_cookies_faculty) -> None:
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 403


def test_admin_list_users_returns_all_users(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    # Create additional users
    create_user(
        db_session,
        name="Faculty One",
        email="faculty1@test.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    create_user(
        db_session,
        name="Faculty Two",
        email="faculty2@test.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    _auth(client, auth_cookies_admin)
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] >= 3  # admin + 2 faculty
    assert len(data["items"]) >= 3
    # Verify structure
    for item in data["items"]:
        assert "user_id" in item
        assert "name" in item
        assert "email" in item
        assert "role" in item
        assert "is_active" in item
        assert "created_at" in item


def test_admin_create_user_requires_admin(client: TestClient, auth_cookies_faculty) -> None:
    payload = {
        "name": "New Faculty",
        "email": "newfaculty@test.com",
        "password": "password123",
        "role": "faculty",
    }
    response = client.post("/api/v1/admin/users", json=payload)
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.post("/api/v1/admin/users", json=payload)
    assert response.status_code == 403


def test_admin_create_faculty_user(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _auth(client, auth_cookies_admin)
    payload = {
        "name": "New Faculty",
        "email": "newfaculty@test.com",
        "password": "password123",
        "role": "faculty",
    }
    response = client.post("/api/v1/admin/users", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "New Faculty"
    assert data["email"] == "newfaculty@test.com"
    assert data["role"] == "faculty"
    assert data["is_active"] is True

    # Verify persisted in DB
    from server.modules.auth.models import User
    user = db_session.query(User).filter_by(email="newfaculty@test.com").first()
    assert user is not None
    assert user.name == "New Faculty"


def test_admin_create_user_duplicate_email(
    client: TestClient, auth_cookies_admin
) -> None:
    _auth(client, auth_cookies_admin)
    payload = {
        "name": "Admin User",
        "email": "admin@example.com",  # already exists from fixture
        "password": "password123",
        "role": "faculty",
    }
    response = client.post("/api/v1/admin/users", json=payload)
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# System summary endpoint tests
# ---------------------------------------------------------------------------

def test_admin_summary_requires_admin(client: TestClient, auth_cookies_faculty) -> None:
    response = client.get("/api/v1/admin/summary")
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.get("/api/v1/admin/summary")
    assert response.status_code == 403


def test_admin_summary_returns_counts(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    # Seed a faculty user so we have a non-zero count
    create_user(
        db_session,
        name="Summary Faculty",
        email="summary-faculty@test.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    _auth(client, auth_cookies_admin)
    response = client.get("/api/v1/admin/summary")
    assert response.status_code == 200

    data = response.json()
    assert "total_documents" in data
    assert "total_faculty" in data
    assert "active_evaluations" in data
    assert "failed_evaluations" in data
    # We seeded a faculty user above
    assert data["total_faculty"] >= 1
