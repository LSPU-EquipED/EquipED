"""Self-service registration and OTP verification flows."""

from __future__ import annotations

import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .crypto import _otp_hash, hash_password, hash_session_token
from .email_policy import normalize_lspu_email
from .models import AccountStatus, PendingRegistration, User, UserRole


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def start_registration(
    db: Session,
    *,
    payload: Any,
    settings: Any = None,
) -> tuple[str, PendingRegistration, str]:
    normalized_email = normalize_lspu_email(payload.email)
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        if existing.role == UserRole.ADMIN:
            raise ValueError("An account with this email already exists")
        if existing.account_status != AccountStatus.REJECTED:
            raise ValueError("An account with this email already exists")

    registration_token = secrets.token_urlsafe(32)
    otp = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(UTC)

    # Check if there is an existing pending registration row for this email
    existing_reg = db.scalar(
        select(PendingRegistration)
        .where(PendingRegistration.email == normalized_email)
        .with_for_update()
    )
    if existing_reg is not None:
        # Enforce 60s cooldown from last_sent_at
        if now - _utc(existing_reg.last_sent_at) < timedelta(seconds=60):
            raise ValueError("Please wait before requesting another code")

        # Reuse existing row, update attributes and OTP
        existing_reg.token_hash = hash_session_token(registration_token)
        existing_reg.existing_user_id = (
            existing.user_id if existing is not None else None
        )
        existing_reg.name = payload.name.strip()
        existing_reg.password_hash = hash_password(payload.password)
        existing_reg.faculty_id = payload.faculty_id.strip()
        existing_reg.department = payload.department.strip()
        existing_reg.program = payload.program.strip()
        existing_reg.otp_hash = _otp_hash(otp)
        existing_reg.otp_expires_at = now + timedelta(minutes=10)
        existing_reg.otp_attempts = 0
        existing_reg.last_sent_at = now
        registration = existing_reg
    else:
        registration = PendingRegistration(
            token_hash=hash_session_token(registration_token),
            existing_user_id=existing.user_id if existing is not None else None,
            name=payload.name.strip(),
            email=normalized_email,
            password_hash=hash_password(payload.password),
            faculty_id=payload.faculty_id.strip(),
            department=payload.department.strip(),
            program=payload.program.strip(),
            otp_hash=_otp_hash(otp),
            otp_expires_at=now + timedelta(minutes=10),
            otp_attempts=0,
            last_sent_at=now,
        )
        db.add(registration)

    db.flush()
    return registration_token, registration, otp


def verify_registration(db: Session, *, token: str, otp: str) -> User:
    """Verifies OTP and completes faculty registration.

    Lock order:
    1. Existing User row (via SELECT ... FOR UPDATE) if matching.
    2. PendingRegistration row (via SELECT ... FOR UPDATE).
    3. Any Session effects.
    For new users without an existing User row, concurrency relies on
    DB unique constraints on email.
    """
    token_hash = hash_session_token(token)

    # 1. Probe PendingRegistration projection without ORM identity-map caching
    probe_row = db.execute(
        select(
            PendingRegistration.existing_user_id,
            PendingRegistration.email,
        ).where(PendingRegistration.token_hash == token_hash)
    ).first()
    if probe_row is None:
        raise ValueError("Registration is invalid or expired")

    probe_existing_user_id, probe_email = probe_row[0], probe_row[1]

    # 2. Acquire lock on existing User row BEFORE acquiring PendingRegistration lock
    user: User | None = None
    if probe_existing_user_id is not None:
        user = db.scalar(
            select(User).where(User.user_id == probe_existing_user_id).with_for_update()
        )
    else:
        user = db.scalar(
            select(User).where(User.email == probe_email).with_for_update()
        )

    # 3. Acquire lock on PendingRegistration row with fresh refresh and verify coherence
    registration = db.scalar(
        select(PendingRegistration)
        .where(PendingRegistration.token_hash == token_hash)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        registration is None
        or registration.email != probe_email
        or registration.existing_user_id != probe_existing_user_id
    ):
        raise ValueError("Registration is invalid or expired")

    if _utc(registration.otp_expires_at) <= datetime.now(UTC):
        raise ValueError("Verification code has expired")
    if registration.otp_attempts >= 5:
        raise ValueError("Too many verification attempts")

    if not hmac.compare_digest(registration.otp_hash, _otp_hash(otp)):
        registration.otp_attempts += 1
        db.flush()
        raise ValueError("Invalid verification code")

    # 4. Revalidate under lock
    if registration.existing_user_id is not None:
        if (
            user is None
            or user.user_id != registration.existing_user_id
            or user.email != registration.email
        ):
            raise ValueError("Registration is invalid or expired")
        if user.role != UserRole.FACULTY:
            raise ValueError("Only faculty registrations can be verified")
        if user.account_status != AccountStatus.REJECTED:
            raise ValueError("An account with this email already exists")
    else:
        if user is not None:
            if user.role != UserRole.FACULTY:
                raise ValueError("Only faculty registrations can be verified")
            if user.account_status != AccountStatus.REJECTED:
                raise ValueError("An account with this email already exists")
        else:
            user = User(email=registration.email, role=UserRole.FACULTY)
            db.add(user)

    user.name = registration.name
    user.password_hash = registration.password_hash
    user.is_active = False
    user.account_status = AccountStatus.PENDING
    user.faculty_id = registration.faculty_id
    user.department = registration.department
    user.program = registration.program
    user.reviewed_by = None
    user.reviewed_at = None
    user.approved_at = None

    db.delete(registration)
    db.flush()
    return user


def resend_registration_otp(
    db: Session,
    *,
    token: str,
    settings: Any = None,
) -> tuple[PendingRegistration, str]:
    registration = db.scalar(
        select(PendingRegistration)
        .where(PendingRegistration.token_hash == hash_session_token(token))
        .with_for_update()
    )
    if registration is None:
        raise ValueError("Registration is invalid or expired")
    now = datetime.now(UTC)
    if now - _utc(registration.last_sent_at) < timedelta(seconds=60):
        raise ValueError("Please wait before requesting another code")
    otp = f"{secrets.randbelow(1_000_000):06d}"
    registration.otp_hash = _otp_hash(otp)
    registration.otp_expires_at = now + timedelta(minutes=10)
    registration.otp_attempts = 0
    registration.last_sent_at = now
    db.flush()
    return registration, otp


__all__ = [
    "_utc",
    "resend_registration_otp",
    "start_registration",
    "verify_registration",
]
