"""Admin user management tests: list, create, access control."""

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


def test_admin_list_users_requires_admin(
    client: TestClient, auth_cookies_faculty
) -> None:
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
        email="faculty1@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    create_user(
        db_session,
        name="Faculty Two",
        email="faculty2@lspu.edu.ph",
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


def test_admin_create_user_requires_admin(
    client: TestClient, auth_cookies_faculty
) -> None:
    payload = {
        "name": "New Faculty",
        "email": "newfaculty@lspu.edu.ph",
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
        "email": "newfaculty@lspu.edu.ph",
        "password": "password123",
        "role": "faculty",
    }
    response = client.post("/api/v1/admin/users", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "New Faculty"
    assert data["email"] == "newfaculty@lspu.edu.ph"
    assert data["role"] == "faculty"
    assert data["is_active"] is True

    # Verify persisted in DB
    from server.modules.auth.models import User

    user = db_session.query(User).filter_by(email="newfaculty@lspu.edu.ph").first()
    assert user is not None
    assert user.name == "New Faculty"


def test_admin_create_user_duplicate_email(
    client: TestClient, auth_cookies_admin
) -> None:
    _auth(client, auth_cookies_admin)
    payload = {
        "name": "Admin User",
        "email": "admin@lspu.edu.ph",  # already exists from fixture
        "password": "password123",
        "role": "faculty",
    }
    response = client.post("/api/v1/admin/users", json=payload)
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Update user tests
# ---------------------------------------------------------------------------


def test_admin_update_user_requires_admin(
    client: TestClient, auth_cookies_faculty, admin_user
) -> None:
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
    payload = {"email": "newemail@lspu.edu.ph"}
    response = client.put(f"/api/v1/admin/users/{user_id}", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == "newemail@lspu.edu.ph"
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
    payload = {"email": "admin@lspu.edu.ph"}  # already taken by admin fixture
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


def test_admin_deactivate_user_requires_admin(
    client: TestClient, auth_cookies_faculty, faculty_user
) -> None:
    user_id = str(faculty_user.user_id)
    response = client.delete(f"/api/v1/admin/users/{user_id}")
    assert response.status_code == 401

    _auth(client, auth_cookies_faculty)
    response = client.delete(f"/api/v1/admin/users/{user_id}")
    assert response.status_code == 403


def test_admin_deactivate_user_deactivates(
    client: TestClient, auth_cookies_admin, admin_user, faculty_user, db_session
) -> None:
    from datetime import UTC, datetime, timedelta

    from server.modules.auth.models import AccountStatus, Session, User

    # Create active session for faculty user
    sess = Session(
        user_id=faculty_user.user_id,
        token_hash="hash_deactivate_session",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(sess)
    db_session.commit()
    sess_id = sess.session_id

    _auth(client, auth_cookies_admin)
    user_id = str(faculty_user.user_id)
    response = client.delete(f"/api/v1/admin/users/{user_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["is_active"] is False
    assert data["account_status"] == AccountStatus.SUSPENDED.value
    assert data["user_id"] == user_id
    assert data["reviewed_at"] is not None

    # Confirm persisted in DB
    db_user = db_session.query(User).filter_by(user_id=faculty_user.user_id).first()
    assert db_user is not None
    assert db_user.is_active is False
    assert db_user.account_status == AccountStatus.SUSPENDED
    assert db_user.reviewed_by == admin_user.user_id
    assert db_user.reviewed_at is not None

    # Confirm session was revoked
    db_sess = db_session.query(Session).filter_by(session_id=sess_id).first()
    assert db_sess.revoked_at is not None
    revoked_at = db_sess.revoked_at

    # Reapproval preserves revoked session
    resp = client.post(
        f"/api/v1/admin/users/{user_id}/approval",
        json={"status": "approved"},
    )
    assert resp.status_code == 200
    assert resp.json()["account_status"] == AccountStatus.APPROVED.value
    assert resp.json()["is_active"] is True

    db_session.expire_all()
    db_sess = db_session.query(Session).filter_by(session_id=sess_id).first()
    assert db_sess.revoked_at == revoked_at


def test_admin_deactivate_user_not_found(
    client: TestClient, auth_cookies_admin
) -> None:
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
    assert "account_status" in data
    assert "faculty_id" in data
    assert "department" in data
    assert "program" in data
    assert "approved_at" in data
    assert "reviewed_at" in data
    assert "notification_warning" in data
    assert "created_at" in data


# ---------------------------------------------------------------------------
# Approval lifecycle, session revocation, notifications, and DTO tests
# ---------------------------------------------------------------------------


def test_admin_create_user_password_length_bounds(
    client: TestClient, auth_cookies_admin
) -> None:
    _auth(client, auth_cookies_admin)

    # Password too short (< 8 chars)
    resp = client.post(
        "/api/v1/admin/users",
        json={
            "name": "Short Pass",
            "email": "shortpass@lspu.edu.ph",
            "password": "short",
            "role": "faculty",
        },
    )
    assert resp.status_code == 422

    # Password too long (> 256 chars)
    resp = client.post(
        "/api/v1/admin/users",
        json={
            "name": "Long Pass",
            "email": "longpass@lspu.edu.ph",
            "password": "a" * 257,
            "role": "faculty",
        },
    )
    assert resp.status_code == 422

    # Exact min length (8 chars)
    resp = client.post(
        "/api/v1/admin/users",
        json={
            "name": "Min Pass",
            "email": "minpass@lspu.edu.ph",
            "password": "a" * 8,
            "role": "faculty",
        },
    )
    assert resp.status_code == 201

    # Exact max length (256 chars)
    resp = client.post(
        "/api/v1/admin/users",
        json={
            "name": "Max Pass",
            "email": "maxpass@lspu.edu.ph",
            "password": "a" * 256,
            "role": "faculty",
        },
    )
    assert resp.status_code == 201


def test_admin_user_mutations_return_full_allowlisted_dto(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    _auth(client, auth_cookies_admin)
    expected_fields = {
        "user_id",
        "name",
        "email",
        "role",
        "is_active",
        "account_status",
        "faculty_id",
        "department",
        "program",
        "approved_at",
        "reviewed_at",
        "notification_warning",
        "created_at",
    }

    # 1. Create mutation
    create_resp = client.post(
        "/api/v1/admin/users",
        json={
            "name": "DTO Test User",
            "email": "dtouser@lspu.edu.ph",
            "password": "validpassword123",
            "role": "faculty",
        },
    )
    assert create_resp.status_code == 201
    create_data = create_resp.json()
    assert expected_fields.issubset(create_data.keys())
    user_id = create_data["user_id"]

    # 2. Update mutation
    update_resp = client.put(
        f"/api/v1/admin/users/{user_id}",
        json={"name": "DTO Test User Updated"},
    )
    assert update_resp.status_code == 200
    update_data = update_resp.json()
    assert expected_fields.issubset(update_data.keys())

    # 3. Approval mutation
    approval_resp = client.post(
        f"/api/v1/admin/users/{user_id}/approval",
        json={"status": "approved"},
    )
    assert approval_resp.status_code == 200
    approval_data = approval_resp.json()
    assert expected_fields.issubset(approval_data.keys())

    # 4. Deactivate mutation
    deactivate_resp = client.delete(f"/api/v1/admin/users/{user_id}")
    assert deactivate_resp.status_code == 200
    deactivate_data = deactivate_resp.json()
    assert expected_fields.issubset(deactivate_data.keys())


def test_admin_approval_rbac(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin, faculty_user
) -> None:
    user_id = str(faculty_user.user_id)
    payload = {"status": "approved"}

    # Unauthenticated
    client.cookies.clear()
    resp = client.post(f"/api/v1/admin/users/{user_id}/approval", json=payload)
    assert resp.status_code == 401

    # Faculty (forbidden)
    _auth(client, auth_cookies_faculty)
    resp = client.post(f"/api/v1/admin/users/{user_id}/approval", json=payload)
    assert resp.status_code == 403

    # Admin (allowed)
    _auth(client, auth_cookies_admin)
    resp = client.post(f"/api/v1/admin/users/{user_id}/approval", json=payload)
    assert resp.status_code == 200


def test_admin_approval_lifecycle_session_revocation_and_no_revival(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    from datetime import UTC, datetime, timedelta

    from server.modules.auth.models import AccountStatus, Session

    # Create an approved faculty user
    user = create_user(
        db_session,
        name="Lifecycle Faculty",
        email="lifecycle@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    user.account_status = AccountStatus.APPROVED
    user.is_active = True
    db_session.commit()
    user_id = user.user_id

    # Create active session 1 for user
    sess1 = Session(
        user_id=user_id,
        token_hash="hash_session_1",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(sess1)
    db_session.commit()
    sess1_id = sess1.session_id

    _auth(client, auth_cookies_admin)

    # 1. Admin suspends user: session 1 must be revoked, user becomes inactive
    resp = client.post(
        f"/api/v1/admin/users/{user_id}/approval",
        json={"status": "suspended"},
    )
    assert resp.status_code == 200
    assert resp.json()["account_status"] == "suspended"
    assert resp.json()["is_active"] is False

    db_sess1 = db_session.query(Session).filter_by(session_id=sess1_id).first()
    assert db_sess1.revoked_at is not None
    sess1_revoked_at = db_sess1.revoked_at

    # 2. Admin reapproves user: user is active, but session 1 is NOT revived
    resp = client.post(
        f"/api/v1/admin/users/{user_id}/approval",
        json={"status": "approved"},
    )
    assert resp.status_code == 200
    assert resp.json()["account_status"] == "approved"
    assert resp.json()["is_active"] is True

    db_session.expire_all()
    db_sess1 = db_session.query(Session).filter_by(session_id=sess1_id).first()
    assert db_sess1.revoked_at == sess1_revoked_at  # Revocation preserved

    # 3. Create active session 2 for user, then reject
    sess2 = Session(
        user_id=user_id,
        token_hash="hash_session_2",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(sess2)
    db_session.commit()
    sess2_id = sess2.session_id

    resp = client.post(
        f"/api/v1/admin/users/{user_id}/approval",
        json={"status": "rejected"},
    )
    assert resp.status_code == 200
    assert resp.json()["account_status"] == "rejected"
    assert resp.json()["is_active"] is False

    db_session.expire_all()
    db_sess2 = db_session.query(Session).filter_by(session_id=sess2_id).first()
    assert db_sess2.revoked_at is not None


def test_admin_approval_notification_background_tasks_and_failure_resilience(
    client: TestClient, auth_cookies_admin, db_session, monkeypatch, caplog
) -> None:
    from server.modules.auth.models import AccountStatus, User

    # Create pending faculty user
    user = create_user(
        db_session,
        name="Pending Faculty",
        email="pending_notify@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    user.account_status = AccountStatus.PENDING
    user.is_active = False
    db_session.commit()
    user_id = user.user_id

    # Mock send_status_email to simulate failure
    def mock_failing_send_status_email(*args, **kwargs):
        raise RuntimeError("SMTP connection failed")

    monkeypatch.setattr(
        "server.modules.admin.router.send_status_email",
        mock_failing_send_status_email,
    )

    _auth(client, auth_cookies_admin)

    import logging

    with caplog.at_level(logging.WARNING):
        resp = client.post(
            f"/api/v1/admin/users/{user_id}/approval",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["account_status"] == "approved"
        assert resp.json()["is_active"] is True

    # Confirm DB change persisted despite notification failure
    db_user = db_session.query(User).filter_by(user_id=user_id).first()
    assert db_user.account_status == AccountStatus.APPROVED
    assert db_user.is_active is True

    # Confirm bounded generic warning logged without sensitive leaks
    assert "Account status notification delivery failed." in caplog.text
    assert "pending_notify@lspu.edu.ph" not in caplog.text


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
        email="throwaway@lspu.edu.ph",
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


def test_admin_hard_delete_user_not_found(
    client: TestClient, auth_cookies_admin
) -> None:
    _auth(client, auth_cookies_admin)
    import uuid

    fake_id = str(uuid.uuid4())
    response = client.delete(f"/api/v1/admin/users/{fake_id}/permanent")
    assert response.status_code == 404


def test_admin_hard_delete_returns_no_body(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    """204 response should have no body."""
    throwaway = create_user(
        db_session,
        name="Throwaway2",
        email="throwaway2@lspu.edu.ph",
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
        email="throwaway3@lspu.edu.ph",
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


# ---------------------------------------------------------------------------
# Concurrency and row locking tests
# ---------------------------------------------------------------------------


def test_user_service_mutations_use_with_for_update(db_session, faculty_user) -> None:
    """Ensure mutations issue SELECT ... FOR UPDATE queries."""
    from server.modules.admin.user_service import (
        deactivate_user,
        hard_delete_user,
        update_user,
    )
    from sqlalchemy.sql import Select

    captured_stmts: list[Select] = []
    original_scalar = db_session.scalar

    def tracking_scalar(stmt, *args, **kwargs):
        if isinstance(stmt, Select):
            captured_stmts.append(stmt)
        return original_scalar(stmt, *args, **kwargs)

    db_session.scalar = tracking_scalar
    try:
        # 1. update_user
        captured_stmts.clear()
        update_user(db_session, faculty_user.user_id, name="Lock Name")
        assert any(
            isinstance(s, Select) and s._for_update_arg is not None
            for s in captured_stmts
        )

        # 2. deactivate_user
        captured_stmts.clear()
        deactivate_user(db_session, faculty_user.user_id)
        assert any(
            isinstance(s, Select) and s._for_update_arg is not None
            for s in captured_stmts
        )

        # 3. hard_delete_user
        captured_stmts.clear()
        hard_delete_user(db_session, faculty_user.user_id)
        assert any(
            isinstance(s, Select) and s._for_update_arg is not None
            for s in captured_stmts
        )
    finally:
        db_session.scalar = original_scalar


def test_admin_approval_endpoint_user_not_found(
    client: TestClient, auth_cookies_admin
) -> None:
    """Approval endpoint returns 404 when target user does not exist."""
    import uuid

    _auth(client, auth_cookies_admin)
    fake_id = str(uuid.uuid4())
    resp = client.post(
        f"/api/v1/admin/users/{fake_id}/approval",
        json={"status": "approved"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"
