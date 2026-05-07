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

from .exceptions import InactiveUserError, InvalidCredentialsError
from .models import Session as AuthSession
from .models import User, UserRole

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

    admin_exists = db.scalar(
        select(User.user_id).where(User.role == UserRole.ADMIN).limit(1)
    )
    if admin_exists is not None:
        return False

    existing_user = db.scalar(
        select(User).where(User.email == settings.bootstrap_admin_email.lower())
    )
    if existing_user is not None:
        return False

    create_user(
        db,
        name=settings.bootstrap_admin_name,
        email=settings.bootstrap_admin_email,
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

    if not user.is_active:
        raise InactiveUserError("User account is inactive")

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
    if session is None or session.user is None or not session.user.is_active:
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
