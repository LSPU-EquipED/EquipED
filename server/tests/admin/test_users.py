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


# ---------------------------------------------------------------------------
# Update user tests
# ---------------------------------------------------------------------------


def test_admin_update_user_requires_admin(client: TestClient, auth_cookies_faculty, admin_user) -> None:
    user_id = str(admin_user.user_id)
    payload = {"name": "Updated Name"}
    response = client.put(f"/api/v1/admin/users/{user_id}", json=payload)
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.put(f"/api/v1/admin/users/{user_id}", json=payload)
    assert response.status_code == 403


def test_admin_update_user_name(
    client: TestClient, auth_cookies_admin, faculty_user
) -> None:
    _auth(client, auth_cookies_admin)
    user_id = str(faculty_user.user_id)
    payload = {"name": "Updated Faculty Name"}
    response = client.put(f"/api/v1/admin/users/{user_id}", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "Updated Faculty Name"
    assert data["email"] == faculty_user.email
    assert data["is_active"] is True


def test_admin_update_user_email(
    client: TestClient, auth_cookies_admin, faculty_user
) -> None:
    _auth(client, auth_cookies_admin)
    user_id = str(faculty_user.user_id)
    payload = {"email": "newemail@test.com"}
    response = client.put(f"/api/v1/admin/users/{user_id}", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == "newemail@test.com"
    assert data["name"] == faculty_user.name


def test_admin_update_user_deactivate(
    client: TestClient, auth_cookies_admin, faculty_user
) -> None:
    _auth(client, auth_cookies_admin)
    user_id = str(faculty_user.user_id)
    payload = {"is_active": False}
    response = client.put(f"/api/v1/admin/users/{user_id}", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["is_active"] is False


def test_admin_update_user_not_found(client: TestClient, auth_cookies_admin) -> None:
    _auth(client, auth_cookies_admin)
    import uuid
    fake_id = str(uuid.uuid4())
    payload = {"name": "Ghost"}
    response = client.put(f"/api/v1/admin/users/{fake_id}", json=payload)
    assert response.status_code == 404


def test_admin_update_user_duplicate_email(
    client: TestClient, auth_cookies_admin, faculty_user
) -> None:
    """Cannot update a user's email to one already in use."""
    _auth(client, auth_cookies_admin)
    user_id = str(faculty_user.user_id)
    payload = {"email": "admin@example.com"}  # already taken by admin fixture
    response = client.put(f"/api/v1/admin/users/{user_id}", json=payload)
    assert response.status_code == 409


def test_admin_update_user_no_fields(
    client: TestClient, auth_cookies_admin, faculty_user
) -> None:
    """Sending an empty body is a no-op (200, unchanged)."""
    _auth(client, auth_cookies_admin)
    user_id = str(faculty_user.user_id)
    response = client.put(f"/api/v1/admin/users/{user_id}", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == faculty_user.name
    assert data["email"] == faculty_user.email


# ---------------------------------------------------------------------------
# Deactivate user tests
# ---------------------------------------------------------------------------


def test_admin_deactivate_user_requires_admin(client: TestClient, auth_cookies_faculty, faculty_user) -> None:
    user_id = str(faculty_user.user_id)
    response = client.delete(f"/api/v1/admin/users/{user_id}")
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.delete(f"/api/v1/admin/users/{user_id}")
    assert response.status_code == 403


def test_admin_deactivate_user_deactivates(
    client: TestClient, auth_cookies_admin, faculty_user, db_session
) -> None:
    _auth(client, auth_cookies_admin)
    user_id = str(faculty_user.user_id)
    response = client.delete(f"/api/v1/admin/users/{user_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["is_active"] is False
    assert data["user_id"] == user_id

    # Confirm persisted in DB
    from server.modules.auth.models import User
    db_user = db_session.query(User).filter_by(user_id=faculty_user.user_id).first()
    assert db_user is not None
    assert db_user.is_active is False


def test_admin_deactivate_user_not_found(client: TestClient, auth_cookies_admin) -> None:
    _auth(client, auth_cookies_admin)
    import uuid
    fake_id = str(uuid.uuid4())
    response = client.delete(f"/api/v1/admin/users/{fake_id}")
    assert response.status_code == 404


def test_admin_deactivate_user_returns_user_data(
    client: TestClient, auth_cookies_admin, faculty_user
) -> None:
    """DELETE response should include the full user record."""
    _auth(client, auth_cookies_admin)
    user_id = str(faculty_user.user_id)
    response = client.delete(f"/api/v1/admin/users/{user_id}")
    assert response.status_code == 200

    data = response.json()
    assert "user_id" in data
    assert "name" in data
    assert "email" in data
    assert "role" in data
    assert "is_active" in data
    assert "created_at" in data


# ---------------------------------------------------------------------------
# Hard delete (permanent) user tests
# ---------------------------------------------------------------------------


def test_admin_hard_delete_user_requires_admin(
    client: TestClient, auth_cookies_faculty, admin_user
) -> None:
    user_id = str(admin_user.user_id)
    response = client.delete(f"/api/v1/admin/users/{user_id}/permanent")
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.delete(f"/api/v1/admin/users/{user_id}/permanent")
    assert response.status_code == 403


def test_admin_hard_delete_user_removes_from_db(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    """Hard delete permanently removes the user row."""
    from server.modules.auth.models import User

    # Create a throwaway user to delete
    throwaway = create_user(
        db_session,
        name="Throwaway",
        email="throwaway@test.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    throwaway_id = str(throwaway.user_id)

    _auth(client, auth_cookies_admin)
    response = client.delete(f"/api/v1/admin/users/{throwaway_id}/permanent")
    assert response.status_code == 204

    # Confirm row is gone
    db_user = db_session.query(User).filter_by(user_id=throwaway.user_id).first()
    assert db_user is None


def test_admin_hard_delete_user_not_found(client: TestClient, auth_cookies_admin) -> None:
    _auth(client, auth_cookies_admin)
    import uuid
    fake_id = str(uuid.uuid4())
    response = client.delete(f"/api/v1/admin/users/{fake_id}/permanent")
    assert response.status_code == 404


def test_admin_hard_delete_returns_no_body(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    """204 response should have no body."""
    from server.modules.auth.models import User

    throwaway = create_user(
        db_session,
        name="Throwaway2",
        email="throwaway2@test.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    throwaway_id = str(throwaway.user_id)

    _auth(client, auth_cookies_admin)
    response = client.delete(f"/api/v1/admin/users/{throwaway_id}/permanent")
    assert response.status_code == 204
    assert response.content == b""


def test_admin_hard_delete_user_not_listed_after(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    """After hard delete, user should not appear in user list."""
    throwaway = create_user(
        db_session,
        name="Throwaway3",
        email="throwaway3@test.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    throwaway_id = str(throwaway.user_id)

    _auth(client, auth_cookies_admin)
    response = client.delete(f"/api/v1/admin/users/{throwaway_id}/permanent")
    assert response.status_code == 204

    # Verify absent from list
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 200
    ids = [u["user_id"] for u in response.json()["items"]]
    assert throwaway_id not in ids
