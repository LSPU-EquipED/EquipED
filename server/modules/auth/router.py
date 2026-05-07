"""HTTP routes for local session-based authentication."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from server.core.config import Settings, get_settings
from server.core.database import get_db_session
from sqlalchemy.orm import Session

from .exceptions import InactiveUserError, InvalidCredentialsError
from .schemas import AuthStateResponse, AuthUserResponse, LoginRequest, LoginResponse
from .service import (
    authenticate_user,
    get_authenticated_user_from_token,
    logout_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_user_response(user) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        role=user.role,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    try:
        result = authenticate_user(
            db,
            email=payload.email,
            password=payload.password,
            settings=settings,
        )
    except (InvalidCredentialsError, InactiveUserError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.session_ttl_hours * 3600,
    )
    return LoginResponse(user=_build_user_response(result.user))


@router.post("/logout", response_model=AuthStateResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AuthStateResponse:
    logout_session(db, request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(
        key=settings.session_cookie_name, httponly=True, samesite="lax"
    )
    return AuthStateResponse(authenticated=False, user=None)


@router.get("/me", response_model=AuthStateResponse)
def me(
    request: Request,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AuthStateResponse:
    user = get_authenticated_user_from_token(
        db, request.cookies.get(settings.session_cookie_name)
    )
    if user is None:
        return AuthStateResponse(authenticated=False, user=None)

    return AuthStateResponse(authenticated=True, user=_build_user_response(user))


__all__ = ["router"]
