"""Business logic for local credential auth and persisted sessions."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from server.core.config import Settings
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from .email_policy import normalize_lspu_email
from .exceptions import InactiveUserError, InvalidCredentialsError
from .models import AccountStatus, PendingRegistration, User, UserRole
from .models import Session as AuthSession

SCRYPT_PREFIX = "scrypt"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    display_name: str
    email: str
    role: UserRole


@dataclass(frozen=True)
class LoginResult:
    user: AuthenticatedUser
    session_token: str


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "$".join(
        (
            SCRYPT_PREFIX,
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            salt.hex(),
            derived_key.hex(),
        )
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n_value, r_value, p_value, salt_hex, digest_hex = stored_hash.split(
            "$", 5
        )
    except ValueError:
        return False

    if algorithm != SCRYPT_PREFIX:
        return False

    try:
        expected_digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n_value),
            r=int(r_value),
            p=int(p_value),
            dklen=len(bytes.fromhex(digest_hex)),
        )
    except (TypeError, ValueError):
        return False

    return hmac.compare_digest(expected_digest.hex(), digest_hex)


def build_authenticated_user(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.user_id,
        display_name=user.name,
        email=user.email,
        role=user.role,
    )


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    role: UserRole,
    is_active: bool = True,
) -> User:
    user = User(
        name=name.strip(),
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def bootstrap_admin_if_configured(db: Session, settings: Settings) -> bool:
    if not all(
        (
            settings.bootstrap_admin_email,
            settings.bootstrap_admin_name,
            settings.bootstrap_admin_password,
        )
    ):
        return False

    normalized_email = normalize_lspu_email(settings.bootstrap_admin_email)

    admin_exists = db.scalar(
        select(User.user_id).where(User.role == UserRole.ADMIN).limit(1)
    )
    if admin_exists is not None:
        return False

    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        return False

    create_user(
        db,
        name=settings.bootstrap_admin_name,
        email=normalized_email,
        password=settings.bootstrap_admin_password,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.commit()
    return True


def authenticate_user(
    db: Session, *, email: str, password: str, settings: Settings
) -> LoginResult:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password")

    if not user.is_active or user.account_status != AccountStatus.APPROVED:
        raise InactiveUserError("User account is inactive or awaiting approval")

    session_token = secrets.token_urlsafe(32)
    session = AuthSession(
        user_id=user.user_id,
        token_hash=hash_session_token(session_token),
        expires_at=datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    db.commit()

    return LoginResult(user=build_authenticated_user(user), session_token=session_token)


def get_active_session_query(token: str) -> Select[tuple[AuthSession]]:
    return (
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == hash_session_token(token))
        .where(AuthSession.revoked_at.is_(None))
        .where(AuthSession.expires_at > datetime.now(UTC))
    )


def get_authenticated_user_from_token(
    db: Session, token: str | None
) -> AuthenticatedUser | None:
    if not token:
        return None

    session = db.scalar(get_active_session_query(token))
    if (
        session is None
        or session.user is None
        or not session.user.is_active
        or session.user.account_status != AccountStatus.APPROVED
    ):
        return None

    return build_authenticated_user(session.user)


def logout_session(db: Session, token: str | None) -> bool:
    if not token:
        return False

    session = db.scalar(get_active_session_query(token))
    if session is None:
        return False

    session.revoked_at = datetime.now(UTC)
    db.commit()
    return True


def _otp_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def start_registration(db: Session, *, payload, settings):
    normalized_email = normalize_lspu_email(payload.email)
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None and existing.account_status != AccountStatus.REJECTED:
        raise ValueError("An account with this email already exists")
    previous = db.scalar(
        select(PendingRegistration).where(PendingRegistration.email == normalized_email)
    )
    if previous is not None:
        db.delete(previous)
        db.flush()
    registration_token = secrets.token_urlsafe(32)
    otp = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(UTC)
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
        last_sent_at=now,
    )
    db.add(registration)
    db.commit()
    return registration_token, registration, otp


def verify_registration(db: Session, *, token: str, otp: str):
    registration = db.scalar(
        select(PendingRegistration).where(
            PendingRegistration.token_hash == hash_session_token(token)
        )
    )
    if registration is None:
        raise ValueError("Registration is invalid or expired")
    if _utc(registration.otp_expires_at) <= datetime.now(UTC):
        raise ValueError("Verification code has expired")
    if registration.otp_attempts >= 5:
        raise ValueError("Too many verification attempts")
    registration.otp_attempts += 1
    if not hmac.compare_digest(registration.otp_hash, _otp_hash(otp)):
        db.commit()
        raise ValueError("Invalid verification code")
    user = (
        db.get(User, registration.existing_user_id)
        if registration.existing_user_id
        else None
    )
    if user is None:
        if db.scalar(select(User).where(User.email == registration.email)) is not None:
            raise ValueError("An account with this email already exists")
        user = User(email=registration.email, role=UserRole.FACULTY)
        db.add(user)
    user.name = registration.name
    user.password_hash = registration.password_hash
    user.is_active = False
    user.account_status = AccountStatus.PENDING
    user.faculty_id = registration.faculty_id
    user.department = registration.department
    user.program = registration.program
    db.delete(registration)
    db.commit()
    return user


def resend_registration_otp(db: Session, *, token: str, settings):
    registration = db.scalar(
        select(PendingRegistration).where(
            PendingRegistration.token_hash == hash_session_token(token)
        )
    )
    if registration is None:
        raise ValueError("Registration is invalid or expired")
    if datetime.now(UTC) - _utc(registration.last_sent_at) < timedelta(seconds=60):
        raise ValueError("Please wait before requesting another code")
    otp = f"{secrets.randbelow(1_000_000):06d}"
    registration.otp_hash = _otp_hash(otp)
    registration.otp_expires_at = datetime.now(UTC) + timedelta(minutes=10)
    registration.otp_attempts = 0
    registration.last_sent_at = datetime.now(UTC)
    db.commit()
    return registration, otp


__all__ = [
    "AuthenticatedUser",
    "LoginResult",
    "authenticate_user",
    "bootstrap_admin_if_configured",
    "create_user",
    "get_authenticated_user_from_token",
    "hash_password",
    "logout_session",
    "verify_password",
]
