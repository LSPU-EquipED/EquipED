"""Admin system summary tests: access control, count validation."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.auth.models import UserRole  # noqa: E402
from server.modules.auth.service import create_user  # noqa: E402
from server.tests.admin.conftest import _auth  # noqa: E402


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
        email="summary-faculty@lspu.edu.ph",
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
