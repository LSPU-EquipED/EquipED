"""Auth module endpoint and service tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from server.core.config import Settings
from server.modules.auth.models import Session as AuthSession
from server.modules.auth.models import User, UserRole
from server.modules.auth.service import bootstrap_admin_if_configured
from sqlalchemy import select
from sqlalchemy.orm import Session


def test_me_returns_anonymous_without_session(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "user": None}


def test_login_sets_cookie_and_returns_authenticated_user(
    client: TestClient,
    seeded_user: User,
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "user": {
            "id": str(seeded_user.user_id),
            "displayName": "Platform Admin",
            "email": "admin@example.com",
            "role": "admin",
        },
    }
    assert "equiped_session=" in response.headers["set-cookie"]


def test_me_returns_authenticated_user_after_login(
    client: TestClient,
    seeded_user: User,
) -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )

    assert login_response.status_code == 200

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "user": {
            "id": str(seeded_user.user_id),
            "displayName": "Platform Admin",
            "email": "admin@example.com",
            "role": "admin",
        },
    }


def test_logout_revokes_active_session(
    client: TestClient,
    db_session: Session,
    seeded_user: User,
) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )

    logout_response = client.post("/api/v1/auth/logout")
    me_response = client.get("/api/v1/auth/me")
    stored_session = db_session.scalar(select(AuthSession))

    assert logout_response.status_code == 200
    assert logout_response.json() == {"authenticated": False, "user": None}
    assert me_response.json() == {"authenticated": False, "user": None}
    assert stored_session is not None
    assert stored_session.revoked_at is not None


def test_login_rejects_invalid_credentials(
    client: TestClient, seeded_user: User
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_bootstrap_admin_creates_first_admin(db_session: Session) -> None:
    settings = Settings(
        database_url=None,
        bootstrap_admin_email="bootstrap@example.com",
        bootstrap_admin_name="Bootstrap Admin",
        bootstrap_admin_password="correct-horse-battery",
    )

    created = bootstrap_admin_if_configured(db_session, settings)
    admin_user = db_session.scalar(
        select(User).where(User.email == "bootstrap@example.com")
    )

    assert created is True
    assert admin_user is not None
    assert admin_user.role == UserRole.ADMIN
