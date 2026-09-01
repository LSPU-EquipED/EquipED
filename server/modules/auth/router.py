"""HTTP routes for local session-based authentication."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from server.core.config import Settings, get_settings
from server.core.database import get_db_session
from sqlalchemy.orm import Session

from .email import send_otp_email
from .exceptions import InactiveUserError, InvalidCredentialsError
from .limiter import (
    check_login_limit,
    check_registration_resend_limit,
    check_registration_start_limit,
    check_registration_verify_limit,
    get_client_ip,
)
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
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    client_ip = get_client_ip(request)
    limit_res = check_login_limit(client_ip, payload.email)
    if not limit_res.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(limit_res.retry_after)},
        )

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
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_session),
):
    client_ip = get_client_ip(request)
    limit_res = check_registration_start_limit(client_ip, payload.email)
    if not limit_res.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration requests. Please try again later.",
            headers={"Retry-After": str(limit_res.retry_after)},
        )

    try:
        token, registration, otp = start_registration(
            db, payload=payload, settings=settings
        )
        send_otp_email(
            settings=settings, to=registration.email, name=registration.name, otp=otp
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        status_code = (
            429
            if "wait before" in str(exc).lower()
            else (409 if "already exists" in str(exc) else 422)
        )
        headers = {"Retry-After": "60"} if status_code == 429 else None
        raise HTTPException(
            status_code=status_code, detail=str(exc), headers=headers
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
    request: Request,
    db: Session = Depends(get_db_session),
):
    client_ip = get_client_ip(request)
    limit_res = check_registration_verify_limit(client_ip, token)
    if not limit_res.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification attempts. Please try again later.",
            headers={"Retry-After": str(limit_res.retry_after)},
        )

    try:
        verify_registration(db, token=token, otp=payload.otp)
        db.commit()
    except ValueError as exc:
        db.commit()
        status_code = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if "Too many" in str(exc)
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        headers = (
            {"Retry-After": "60"}
            if status_code == status.HTTP_429_TOO_MANY_REQUESTS
            else None
        )
        raise HTTPException(
            status_code=status_code, detail=str(exc), headers=headers
        ) from exc
    return RegistrationStatusResponse(
        status="pending",
        message="Your email is verified. Your account is waiting for admin approval.",
    )


@router.post(
    "/registrations/{token}/resend-otp", response_model=RegistrationStartedResponse
)
def resend_otp(
    token: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_session),
):
    client_ip = get_client_ip(request)
    limit_res = check_registration_resend_limit(client_ip, token)
    if not limit_res.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many code resend requests. Please try again later.",
            headers={"Retry-After": str(limit_res.retry_after)},
        )

    try:
        registration, otp = resend_registration_otp(db, token=token, settings=settings)
        send_otp_email(
            settings=settings, to=registration.email, name=registration.name, otp=otp
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        status_code = 429 if "wait before" in str(exc).lower() else 422
        headers = {"Retry-After": "60"} if status_code == 429 else None
        raise HTTPException(
            status_code=status_code, detail=str(exc), headers=headers
        ) from exc
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
