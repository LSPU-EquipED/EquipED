"""Shared fixtures for rubric module tests (auth helpers mirror admin tests)."""

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
