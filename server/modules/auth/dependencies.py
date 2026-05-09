"""Dependency helpers for protecting routes with session auth."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from server.core.config import Settings, get_settings
from server.core.database import get_db_session
from sqlalchemy.orm import Session

from .service import AuthenticatedUser, get_authenticated_user_from_token


def require_authenticated_user(
    request: Request,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    user = get_authenticated_user_from_token(
        db, request.cookies.get(settings.session_cookie_name)
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return user


__all__ = ["require_authenticated_user"]
