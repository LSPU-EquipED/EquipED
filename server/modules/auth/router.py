"""HTTP routes for local session-based authentication."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from server.core.config import Settings, get_settings
from server.core.database import get_db_session
from sqlalchemy.orm import Session

from .email import send_otp_email
from .exceptions import InactiveUserError, InvalidCredentialsError
from .schemas import (
    AuthStateResponse,
    AuthUserResponse,
    LoginRequest,
    LoginResponse,
    RegistrationRequest,
    RegistrationStartedResponse,
    RegistrationStatusResponse,
    RegistrationVerifyRequest,
)
from .service import (
    authenticate_user,
    get_authenticated_user_from_token,
    logout_session,
    resend_registration_otp,
    start_registration,
    verify_registration,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


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
        secure=settings.session_cookie_secure,
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


@router.post(
    "/registrations", response_model=RegistrationStartedResponse, status_code=202
)
def register(
    payload: RegistrationRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_session),
):
    try:
        token, registration, otp = start_registration(
            db, payload=payload, settings=settings
        )
        send_otp_email(
            settings=settings, to=registration.email, name=registration.name, otp=otp
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409 if "already exists" in str(exc) else 422, detail=str(exc)
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unable to start faculty registration")
        raise HTTPException(
            status_code=503,
            detail="Verification email could not be sent. Please try again.",
        ) from exc
    return RegistrationStartedResponse(
        registration_token=token,
        email=registration.email,
        message="Verification code sent.",
    )


@router.post("/registrations/{token}/verify", response_model=RegistrationStatusResponse)
def verify_registration_endpoint(
    token: str,
    payload: RegistrationVerifyRequest,
    db: Session = Depends(get_db_session),
):
    try:
        verify_registration(db, token=token, otp=payload.otp)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RegistrationStatusResponse(
        status="pending",
        message="Your email is verified. Your account is waiting for admin approval.",
    )


@router.post(
    "/registrations/{token}/resend-otp", response_model=RegistrationStartedResponse
)
def resend_otp(
    token: str,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_session),
):
    try:
        registration, otp = resend_registration_otp(db, token=token, settings=settings)
        send_otp_email(
            settings=settings, to=registration.email, name=registration.name, otp=otp
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unable to resend faculty registration OTP")
        raise HTTPException(
            status_code=503,
            detail="Verification email could not be sent. Please try again.",
        ) from exc
    return RegistrationStartedResponse(
        registration_token=token,
        email=registration.email,
        message="A new verification code was sent.",
    )


__all__ = ["router"]
