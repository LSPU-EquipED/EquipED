"""Admin user management tests: list, create, access control."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.tests.admin.conftest import _auth


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
