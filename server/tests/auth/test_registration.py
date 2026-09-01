"""Registration and OTP verification coverage."""

from datetime import UTC, datetime, timedelta

import pytest
from server.modules.auth.limiter import (
    check_login_limit,
    check_registration_resend_limit,
    check_registration_start_limit,
    check_registration_verify_limit,
    reset_auth_limiters,
)
from server.modules.auth.models import (
    AccountStatus,
    PendingRegistration,
    User,
    UserRole,
)
from server.modules.auth.models import (
    Session as AuthSession,
)
from server.modules.auth.schemas import RegistrationRequest
from server.modules.auth.service import (
    authenticate_user,
    create_user,
    hash_session_token,
    revoke_active_sessions,
    start_registration,
    verify_password,
    verify_registration,
)


def test_registration_verifies_otp_before_creating_user(
    client, db_session, monkeypatch
):
    sent = {}

    def capture_email(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("server.modules.auth.router.send_otp_email", capture_email)
    response = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "New Faculty",
            "email": "new.faculty@lspu.edu.ph",
            "password": "secure-password",
            "faculty_id": "FAC-100",
            "department": "College of Computer Studies",
            "program": "BSCS",
        },
    )
    assert response.status_code == 202
    assert (
        db_session.query(User).filter_by(email="new.faculty@lspu.edu.ph").first()
        is None
    )
    assert db_session.query(PendingRegistration).count() == 1

    verify = client.post(
        f"/api/v1/auth/registrations/{response.json()['registration_token']}/verify",
        json={"otp": sent["otp"]},
    )
    assert verify.status_code == 200
    user = db_session.query(User).filter_by(email="new.faculty@lspu.edu.ph").one()
    assert user.account_status == AccountStatus.PENDING
    assert user.is_active is False


def test_registration_rejects_non_lspu_email(client):
    response = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "External User",
            "email": "external@example.com",
            "password": "secure-password",
            "faculty_id": "FAC-101",
            "department": "Office",
            "program": "BSCS",
        },
    )
    assert response.status_code == 422


def test_registration_delivery_failure_rolls_back_start(
    client, db_session, monkeypatch
):
    def failing_send_email(**kwargs):
        raise RuntimeError("SMTP connection dropped")

    monkeypatch.setattr("server.modules.auth.router.send_otp_email", failing_send_email)
    response = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "Failed Delivery Faculty",
            "email": "failed.delivery@lspu.edu.ph",
            "password": "secure-password",
            "faculty_id": "FAC-102",
            "department": "College of Computer Studies",
            "program": "BSCS",
        },
    )
    assert response.status_code == 503
    # No PendingRegistration row should be committed
    assert (
        db_session.query(PendingRegistration)
        .filter_by(email="failed.delivery@lspu.edu.ph")
        .first()
        is None
    )


def test_resend_delivery_failure_rolls_back_resend(client, db_session, monkeypatch):
    sent = {}

    def capture_email(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("server.modules.auth.router.send_otp_email", capture_email)
    response = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "Resend Test Faculty",
            "email": "resend.test@lspu.edu.ph",
            "password": "secure-password",
            "faculty_id": "FAC-103",
            "department": "College of Computer Studies",
            "program": "BSCS",
        },
    )
    assert response.status_code == 202
    token = response.json()["registration_token"]
    original_otp = sent["otp"]

    # Age the registration past 60s so resend is allowed
    reg = (
        db_session.query(PendingRegistration)
        .filter_by(email="resend.test@lspu.edu.ph")
        .one()
    )
    reg.last_sent_at = datetime.now(UTC) - timedelta(seconds=70)
    db_session.commit()
    reset_auth_limiters()

    # Now make email sending fail for resend
    def failing_send_email(**kwargs):
        raise RuntimeError("SMTP connection dropped")

    monkeypatch.setattr("server.modules.auth.router.send_otp_email", failing_send_email)
    resend_resp = client.post(f"/api/v1/auth/registrations/{token}/resend-otp")
    assert resend_resp.status_code == 503

    # State in db should not have updated otp_attempts or broken original verification
    db_session.expire_all()
    # The original OTP should still work if we verify it
    monkeypatch.setattr("server.modules.auth.router.send_otp_email", capture_email)
    verify_resp = client.post(
        f"/api/v1/auth/registrations/{token}/verify",
        json={"otp": original_otp},
    )
    assert verify_resp.status_code == 200


def test_registration_start_cooldown_enforcement_and_reuse(
    client, db_session, monkeypatch
):
    sent = {}

    def capture_email(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("server.modules.auth.router.send_otp_email", capture_email)
    payload = {
        "name": "Cooldown Faculty",
        "email": "cooldown.faculty@lspu.edu.ph",
        "password": "secure-password",
        "faculty_id": "FAC-104",
        "department": "College of Computer Studies",
        "program": "BSCS",
    }
    resp1 = client.post("/api/v1/auth/registrations", json=payload)
    assert resp1.status_code == 202
    token1 = resp1.json()["registration_token"]

    # Immediate second start attempt must be rate-limited / rejected with 429
    resp2 = client.post("/api/v1/auth/registrations", json=payload)
    assert resp2.status_code == 429
    assert "Retry-After" in resp2.headers

    # Only 1 pending row exists
    assert (
        db_session.query(PendingRegistration)
        .filter_by(email="cooldown.faculty@lspu.edu.ph")
        .count()
        == 1
    )

    # After cooldown expires, start reuses and updates row without duplicate
    reg = (
        db_session.query(PendingRegistration)
        .filter_by(email="cooldown.faculty@lspu.edu.ph")
        .one()
    )
    reg.last_sent_at = datetime.now(UTC) - timedelta(seconds=65)
    db_session.commit()
    reset_auth_limiters()

    payload["name"] = "Cooldown Faculty Renamed"
    resp3 = client.post("/api/v1/auth/registrations", json=payload)
    assert resp3.status_code == 202
    token3 = resp3.json()["registration_token"]
    assert token3 != token1

    assert (
        db_session.query(PendingRegistration)
        .filter_by(email="cooldown.faculty@lspu.edu.ph")
        .count()
        == 1
    )
    updated_reg = (
        db_session.query(PendingRegistration)
        .filter_by(email="cooldown.faculty@lspu.edu.ph")
        .one()
    )
    assert updated_reg.name == "Cooldown Faculty Renamed"


def test_verification_attempt_persistence_and_max_attempts(
    client, db_session, monkeypatch
):
    sent = {}

    def capture_email(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("server.modules.auth.router.send_otp_email", capture_email)
    resp = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "Attempts Faculty",
            "email": "attempts.faculty@lspu.edu.ph",
            "password": "secure-password",
            "faculty_id": "FAC-105",
            "department": "College of Computer Studies",
            "program": "BSCS",
        },
    )
    assert resp.status_code == 202
    token = resp.json()["registration_token"]
    correct_otp = sent["otp"]
    bad_otp = "000000" if correct_otp != "000000" else "111111"

    # Send 5 incorrect attempts
    for i in range(1, 6):
        fail_resp = client.post(
            f"/api/v1/auth/registrations/{token}/verify",
            json={"otp": bad_otp},
        )
        assert fail_resp.status_code in (422, 429)
        reg = (
            db_session.query(PendingRegistration)
            .filter_by(email="attempts.faculty@lspu.edu.ph")
            .one()
        )
        assert reg.otp_attempts == i

    # 6th attempt with correct OTP should be rejected due to max attempts exceeded
    locked_resp = client.post(
        f"/api/v1/auth/registrations/{token}/verify",
        json={"otp": correct_otp},
    )
    assert locked_resp.status_code == 429
    assert locked_resp.headers.get("Retry-After") == "60"
    assert "Too many" in locked_resp.text
    # User should NOT have been created
    assert (
        db_session.query(User).filter_by(email="attempts.faculty@lspu.edu.ph").first()
        is None
    )


def test_public_registration_rejects_existing_admin_email(client, db_session):
    # Create an admin
    create_user(
        db_session,
        name="Existing Admin",
        email="admin.user@lspu.edu.ph",
        password="admin-password",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "Imposter Admin",
            "email": "admin.user@lspu.edu.ph",
            "password": "secure-password",
            "faculty_id": "FAC-999",
            "department": "Admin Office",
            "program": "Admin",
        },
    )
    assert resp.status_code == 409


def test_rejected_faculty_can_reregister_and_resets_approval_state(
    client, db_session, monkeypatch
):
    # Create an existing rejected faculty member
    user = create_user(
        db_session,
        name="Rejected Faculty",
        email="rejected.faculty@lspu.edu.ph",
        password="old-password",
        role=UserRole.FACULTY,
        is_active=False,
    )
    user.account_status = AccountStatus.REJECTED
    user.reviewed_at = datetime.now(UTC) - timedelta(days=1)
    user.approved_at = None
    db_session.commit()

    sent = {}

    def capture_email(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("server.modules.auth.router.send_otp_email", capture_email)
    resp = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "Rejected Faculty Reapplying",
            "email": "rejected.faculty@lspu.edu.ph",
            "password": "new-secure-password",
            "faculty_id": "FAC-200",
            "department": "College of Arts",
            "program": "BA Comm",
        },
    )
    assert resp.status_code == 202
    token = resp.json()["registration_token"]

    verify_resp = client.post(
        f"/api/v1/auth/registrations/{token}/verify",
        json={"otp": sent["otp"]},
    )
    assert verify_resp.status_code == 200

    db_session.expire_all()
    updated_user = (
        db_session.query(User).filter_by(email="rejected.faculty@lspu.edu.ph").one()
    )
    assert updated_user.account_status == AccountStatus.PENDING
    assert updated_user.is_active is False
    assert updated_user.name == "Rejected Faculty Reapplying"
    assert updated_user.department == "College of Arts"
    assert updated_user.reviewed_by is None
    assert updated_user.reviewed_at is None
    assert updated_user.approved_at is None


def test_rate_limiter_login_returns_429_with_retry_after(client):
    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@lspu.edu.ph", "password": "wrong-password"},
        )
        assert resp.status_code == 401

    # 6th attempt triggers rate limiting
    rate_limited_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@lspu.edu.ph", "password": "wrong-password"},
    )
    assert rate_limited_resp.status_code == 429
    assert "Retry-After" in rate_limited_resp.headers
    assert int(rate_limited_resp.headers["Retry-After"]) > 0


def test_rate_limiter_independent_dimensions():
    reset_auth_limiters()

    # 1. Login: One IP across many emails (rotating email attack) -> IP limit triggers
    ip = "192.168.1.100"
    for i in range(20):
        res = check_login_limit(ip, f"user{i}@lspu.edu.ph")
        assert res.allowed is True
    blocked_ip = check_login_limit(ip, "another_user@lspu.edu.ph")
    assert blocked_ip.allowed is False
    assert blocked_ip.retry_after > 0

    # 2. Login: One email across many IPs (botnet attack) -> Email limit triggers
    target_email = "victim@lspu.edu.ph"
    for i in range(5):
        res = check_login_limit(f"10.0.0.{i}", target_email)
        assert res.allowed is True
    blocked_email = check_login_limit("10.0.0.99", target_email)
    assert blocked_email.allowed is False
    assert blocked_email.retry_after > 0

    reset_auth_limiters()

    # 3. Registration Start: One IP across many emails -> IP burst limit triggers
    reg_ip = "192.168.2.1"
    for i in range(10):
        res = check_registration_start_limit(reg_ip, f"new_user{i}@lspu.edu.ph")
        assert res.allowed is True
    blocked_reg_ip = check_registration_start_limit(reg_ip, "new_user99@lspu.edu.ph")
    assert blocked_reg_ip.allowed is False
    assert blocked_reg_ip.retry_after > 0

    # 4. Registration Start: One email across many IPs -> shared cooldown triggers
    reg_email = "single_user@lspu.edu.ph"
    res1 = check_registration_start_limit("10.1.1.1", reg_email)
    assert res1.allowed is True
    res2 = check_registration_start_limit("10.1.1.2", reg_email)
    assert res2.allowed is False

    reset_auth_limiters()

    # 5. Verify: Token across multiple IPs -> Token limit triggers
    tok = "opaque-token-123"
    for i in range(10):
        res = check_registration_verify_limit(f"172.16.0.{i}", tok)
        assert res.allowed is True
    blocked_tok = check_registration_verify_limit("172.16.0.99", tok)
    assert blocked_tok.allowed is False

    # Verify: One IP across multiple tokens -> IP limit triggers
    verify_ip = "172.16.1.1"
    for i in range(20):
        res = check_registration_verify_limit(verify_ip, f"token-{i}")
        assert res.allowed is True
    blocked_verify_ip = check_registration_verify_limit(verify_ip, "token-new")
    assert blocked_verify_ip.allowed is False

    reset_auth_limiters()

    # 6. Resend: Token across multiple IPs -> Cooldown triggers
    resend_tok = "opaque-resend-token"
    resend_1 = check_registration_resend_limit("192.168.5.1", resend_tok)
    assert resend_1.allowed is True
    resend_2 = check_registration_resend_limit("192.168.5.2", resend_tok)
    assert resend_2.allowed is False


def test_revoke_active_sessions_helper(db_session, settings):
    user = create_user(
        db_session,
        name="Session Test Faculty",
        email="session.test@lspu.edu.ph",
        password="secure-password",
        role=UserRole.FACULTY,
        is_active=True,
    )
    db_session.commit()

    # Create 3 active sessions
    now = datetime.now(UTC)
    for i in range(3):
        sess = AuthSession(
            user_id=user.user_id,
            token_hash=hash_session_token(f"token_{i}"),
            expires_at=now + timedelta(hours=24),
            revoked_at=None,
        )
        db_session.add(sess)
    db_session.flush()

    # Revoke sessions without committing
    count = revoke_active_sessions(db_session, user.user_id)
    assert count == 3

    # All sessions should be revoked
    sessions = db_session.query(AuthSession).filter_by(user_id=user.user_id).all()
    for s in sessions:
        assert s.revoked_at is not None


def test_queries_use_with_for_update(db_session, settings):
    executed_stmts = []
    orig_scalar = db_session.scalar

    def spy_scalar(statement, *args, **kwargs):
        executed_stmts.append(statement)
        return orig_scalar(statement, *args, **kwargs)

    db_session.scalar = spy_scalar

    # 1. authenticate_user uses with_for_update
    create_user(
        db_session,
        name="Auth Lock Faculty",
        email="auth.lock@lspu.edu.ph",
        password="secure-password",
        role=UserRole.FACULTY,
        is_active=True,
    )
    user = db_session.query(User).filter_by(email="auth.lock@lspu.edu.ph").one()
    user.account_status = AccountStatus.APPROVED
    db_session.commit()

    executed_stmts.clear()
    authenticate_user(
        db_session,
        email="auth.lock@lspu.edu.ph",
        password="secure-password",
        settings=settings,
    )
    auth_stmts_with_lock = [
        s for s in executed_stmts if getattr(s, "_for_update_arg", None) is not None
    ]
    assert len(auth_stmts_with_lock) >= 1

    # 2. start_registration uses with_for_update for existing PendingRegistration
    payload = RegistrationRequest(
        name="Lock Test",
        email="lock.test@lspu.edu.ph",
        password="secure-password",
        faculty_id="FAC-888",
        department="CCS",
        program="BSCS",
    )
    start_registration(db_session, payload=payload, settings=settings)

    # Age registration past 60s cooldown
    reg = (
        db_session.query(PendingRegistration)
        .filter_by(email="lock.test@lspu.edu.ph")
        .one()
    )
    reg.last_sent_at = datetime.now(UTC) - timedelta(seconds=70)
    db_session.commit()

    executed_stmts.clear()
    start_registration(db_session, payload=payload, settings=settings)
    reg_stmts_with_lock = [
        s for s in executed_stmts if getattr(s, "_for_update_arg", None) is not None
    ]
    assert len(reg_stmts_with_lock) >= 1


def test_verify_registration_lock_order_and_for_update(db_session, settings):
    user = create_user(
        db_session,
        name="Lock Order Faculty",
        email="lock.order@lspu.edu.ph",
        password="secure-password",
        role=UserRole.FACULTY,
        is_active=False,
    )
    user.account_status = AccountStatus.REJECTED
    db_session.commit()

    payload = RegistrationRequest(
        name="Lock Order Renamed",
        email="lock.order@lspu.edu.ph",
        password="secure-password-2",
        faculty_id="FAC-LOCK",
        department="CCS",
        program="BSCS",
    )
    token, reg, otp = start_registration(db_session, payload=payload, settings=settings)
    db_session.commit()

    captured_stmts = []
    orig_scalar = db_session.scalar

    def spy_scalar(statement, *args, **kwargs):
        captured_stmts.append(statement)
        return orig_scalar(statement, *args, **kwargs)

    db_session.scalar = spy_scalar

    verify_registration(db_session, token=token, otp=otp)

    # Filter statements executed during verify_registration
    locked_stmts = [
        s for s in captured_stmts if getattr(s, "_for_update_arg", None) is not None
    ]
    assert len(locked_stmts) >= 2

    # Lock order must be: User row first, then PendingRegistration row
    first_locked_sql = str(locked_stmts[0]).lower()
    second_locked_sql = str(locked_stmts[1]).lower()
    assert "users" in first_locked_sql
    assert "pending_registrations" in second_locked_sql
    assert locked_stmts[1]._execution_options.get("populate_existing") is True


def test_rejected_faculty_reregistration_race_rejection_leaves_user_unchanged(
    client, db_session, monkeypatch
):
    sent = {}

    def capture_email(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("server.modules.auth.router.send_otp_email", capture_email)

    initial_password = "initial-rejected-password"
    user = create_user(
        db_session,
        name="Original Faculty Name",
        email="race.faculty@lspu.edu.ph",
        password=initial_password,
        role=UserRole.FACULTY,
        is_active=False,
    )
    user.account_status = AccountStatus.REJECTED
    user.faculty_id = "FAC-ORIG"
    user.department = "Original Dept"
    user.program = "Original Program"
    db_session.commit()
    user_id = user.user_id

    start_resp = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "New Changed Name",
            "email": "race.faculty@lspu.edu.ph",
            "password": "attempted-new-password",
            "faculty_id": "FAC-NEW",
            "department": "New Dept",
            "program": "New Program",
        },
    )
    assert start_resp.status_code == 202
    token = start_resp.json()["registration_token"]
    otp = sent["otp"]

    # Admin approves the faculty member before OTP verification occurs
    db_session.expire_all()
    user = db_session.query(User).filter_by(user_id=user_id).one()
    user.account_status = AccountStatus.APPROVED
    user.is_active = True
    user.approved_at = datetime.now(UTC)
    db_session.commit()

    # Attempt OTP verification
    verify_resp = client.post(
        f"/api/v1/auth/registrations/{token}/verify",
        json={"otp": otp},
    )
    assert verify_resp.status_code in (409, 422)
    assert "already exists" in verify_resp.text or "Only faculty" in verify_resp.text

    # Verify user remains approved and completely unaffected by registration attempt
    db_session.expire_all()
    user_after = db_session.query(User).filter_by(user_id=user_id).one()
    assert user_after.account_status == AccountStatus.APPROVED
    assert user_after.is_active is True
    assert user_after.name == "Original Faculty Name"
    assert user_after.faculty_id == "FAC-ORIG"
    assert user_after.department == "Original Dept"
    assert user_after.program == "Original Program"
    assert verify_password(initial_password, user_after.password_hash) is True
    assert verify_password("attempted-new-password", user_after.password_hash) is False

    # Ensure no sessions were created
    sessions_count = db_session.query(AuthSession).filter_by(user_id=user_id).count()
    assert sessions_count == 0


def test_rejected_faculty_email_changed_rejection_identity_binding(
    client, db_session, monkeypatch
):
    sent = {}

    def capture_email(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("server.modules.auth.router.send_otp_email", capture_email)

    # 1. Rejected faculty user with email A
    user1 = create_user(
        db_session,
        name="User A Name",
        email="email.a@lspu.edu.ph",
        password="password-user-a",
        role=UserRole.FACULTY,
        is_active=False,
    )
    user1.account_status = AccountStatus.REJECTED
    user1.faculty_id = "FAC-A"
    user1.department = "Dept A"
    user1.program = "Prog A"
    db_session.commit()
    user1_id = user1.user_id

    # 2. User starts registration with email A
    start_resp = client.post(
        "/api/v1/auth/registrations",
        json={
            "name": "User A Renamed",
            "email": "email.a@lspu.edu.ph",
            "password": "new-password-a",
            "faculty_id": "FAC-A-NEW",
            "department": "Dept A New",
            "program": "Prog A New",
        },
    )
    assert start_resp.status_code == 202
    token = start_resp.json()["registration_token"]
    otp = sent["otp"]

    # 3. Admin changes User 1's email to email B while still rejected
    db_session.expire_all()
    user1 = db_session.query(User).filter_by(user_id=user1_id).one()
    user1.email = "email.b@lspu.edu.ph"
    db_session.commit()

    # 4. Another user account (User 2) is assigned email A
    user2 = create_user(
        db_session,
        name="User Two Owner Of A",
        email="email.a@lspu.edu.ph",
        password="password-user-two",
        role=UserRole.FACULTY,
        is_active=True,
    )
    user2.account_status = AccountStatus.APPROVED
    user2.faculty_id = "FAC-TWO"
    user2.department = "Dept Two"
    user2.program = "Prog Two"
    db_session.commit()
    user2_id = user2.user_id

    # 5. Attempt OTP verification using the token for the original registration
    verify_resp = client.post(
        f"/api/v1/auth/registrations/{token}/verify",
        json={"otp": otp},
    )
    assert verify_resp.status_code in (409, 422)

    # 6. Verify User 1 (with email B) is completely untouched
    db_session.expire_all()
    user1_after = db_session.query(User).filter_by(user_id=user1_id).one()
    assert user1_after.email == "email.b@lspu.edu.ph"
    assert user1_after.name == "User A Name"
    assert user1_after.faculty_id == "FAC-A"
    assert user1_after.department == "Dept A"
    assert user1_after.program == "Prog A"
    assert user1_after.account_status == AccountStatus.REJECTED
    assert verify_password("password-user-a", user1_after.password_hash) is True
    assert verify_password("new-password-a", user1_after.password_hash) is False

    # 7. Verify User 2 (owner of email A) is completely untouched
    user2_after = db_session.query(User).filter_by(user_id=user2_id).one()
    assert user2_after.email == "email.a@lspu.edu.ph"
    assert user2_after.name == "User Two Owner Of A"
    assert user2_after.faculty_id == "FAC-TWO"
    assert user2_after.account_status == AccountStatus.APPROVED
    assert verify_password("password-user-two", user2_after.password_hash) is True

    # 8. Ensure no active sessions created for either user
    assert db_session.query(AuthSession).filter_by(user_id=user1_id).count() == 0
    assert db_session.query(AuthSession).filter_by(user_id=user2_id).count() == 0


def test_verify_registration_refreshes_stale_identity_map_state(db_session, settings):
    # 1. Start registration
    payload = RegistrationRequest(
        name="Stale Map Faculty",
        email="stale.map@lspu.edu.ph",
        password="secure-password",
        faculty_id="FAC-STALE",
        department="CCS",
        program="BSCS",
    )
    token, reg, old_otp = start_registration(
        db_session, payload=payload, settings=settings
    )
    db_session.commit()

    # 2. Pre-load the PendingRegistration object into db_session's identity map
    cached_reg = (
        db_session.query(PendingRegistration)
        .filter_by(email="stale.map@lspu.edu.ph")
        .one()
    )
    assert cached_reg.otp_hash is not None

    # 3. Simulate another transaction updating the OTP in the DB
    new_otp = "999888" if old_otp != "999888" else "888777"
    from server.modules.auth.service import _otp_hash

    db_session.execute(
        PendingRegistration.__table__.update()
        .where(PendingRegistration.email == "stale.map@lspu.edu.ph")
        .values(otp_hash=_otp_hash(new_otp))
    )
    db_session.commit()

    # populate_existing=True ensures verify_registration reloads fresh state from DB
    with pytest.raises(ValueError, match="Invalid verification code"):
        verify_registration(db_session, token=token, otp=old_otp)

    # Verifying with the refreshed new_otp succeeds
    verified_user = verify_registration(db_session, token=token, otp=new_otp)
    assert verified_user is not None
    assert verified_user.email == "stale.map@lspu.edu.ph"
