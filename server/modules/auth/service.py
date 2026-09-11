"""Business logic for local credential auth and persisted sessions."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from server.core.config import Settings
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from .crypto import (
    SCRYPT_DKLEN,
    SCRYPT_N,
    SCRYPT_P,
    SCRYPT_PREFIX,
    SCRYPT_R,
    _otp_hash,
    hash_password,
    hash_session_token,
    verify_password,
)
from .email_policy import normalize_lspu_email
from .exceptions import InactiveUserError, InvalidCredentialsError
from .models import AccountStatus, User, UserRole
from .models import Session as AuthSession
from .registration import (
    _utc,
    resend_registration_otp,
    start_registration,
    verify_registration,
)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    display_name: str
    email: str
    role: UserRole
    evaluator_permissions: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoginResult:
    user: AuthenticatedUser
    session_token: str


def build_authenticated_user(user: User) -> AuthenticatedUser:
    raw_perms = getattr(user, "evaluator_permissions", None) or ()
    perms = tuple(raw_perms) if isinstance(raw_perms, (list, tuple)) else ()
    return AuthenticatedUser(
        id=user.user_id,
        display_name=user.name,
        email=user.email,
        role=user.role,
        evaluator_permissions=perms,
    )


def create_user(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    role: UserRole = UserRole.FACULTY,
    is_active: bool = True,
    evaluator_permissions: list[str] | None = None,
) -> User:
    user = User(
        name=name.strip(),
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
        evaluator_permissions=list(evaluator_permissions or []),
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
    user = db.scalar(
        select(User).where(User.email == email.strip().lower()).with_for_update()
    )
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


def revoke_active_sessions(
    db: Session, user_id: UUID, *, revoked_at: datetime | None = None
) -> int:
    """Marks all unrevoked sessions for that user as revoked without committing.

    Admin lane will call this before its transaction commit.
    """
    effective_revoked_at = revoked_at if revoked_at is not None else datetime.now(UTC)
    unrevoked_sessions = db.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == user_id)
        .where(AuthSession.revoked_at.is_(None))
    ).all()
    count = 0
    for session in unrevoked_sessions:
        session.revoked_at = effective_revoked_at
        count += 1
    if count > 0:
        db.flush()
    return count


def logout_session(db: Session, token: str | None) -> bool:
    if not token:
        return False

    session = db.scalar(get_active_session_query(token))
    if session is None:
        return False

    session.revoked_at = datetime.now(UTC)
    db.commit()
    return True


__all__ = [
    "AuthenticatedUser",
    "LoginResult",
    "SCRYPT_DKLEN",
    "SCRYPT_N",
    "SCRYPT_P",
    "SCRYPT_PREFIX",
    "SCRYPT_R",
    "_otp_hash",
    "_utc",
    "authenticate_user",
    "bootstrap_admin_if_configured",
    "build_authenticated_user",
    "create_user",
    "get_active_session_query",
    "get_authenticated_user_from_token",
    "hash_password",
    "hash_session_token",
    "logout_session",
    "resend_registration_otp",
    "revoke_active_sessions",
    "start_registration",
    "verify_password",
    "verify_registration",
]
