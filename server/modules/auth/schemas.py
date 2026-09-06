"""Pydantic schemas for the authentication module."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .email_policy import MAX_EMAIL_LENGTH, normalize_lspu_email
from .models import AccountStatus, UserRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_lspu_email(value)


class RegistrationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    password: str = Field(min_length=8, max_length=256)
    faculty_id: str = Field(min_length=1, max_length=100)
    department: str = Field(min_length=1, max_length=300)
    program: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_lspu_email(value)


class RegistrationStartedResponse(BaseModel):
    registration_token: str
    email: str
    message: str


class RegistrationVerifyRequest(BaseModel):
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class RegistrationStatusResponse(BaseModel):
    status: AccountStatus
    message: str


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    display_name: str = Field(serialization_alias="displayName")
    email: str
    role: UserRole


class AuthStateResponse(BaseModel):
    authenticated: bool
    user: AuthUserResponse | None


class LoginResponse(AuthStateResponse):
    authenticated: bool = True
    user: AuthUserResponse


__all__ = [
    "RegistrationRequest",
    "RegistrationStartedResponse",
    "RegistrationStatusResponse",
    "RegistrationVerifyRequest",
    "AuthStateResponse",
    "AuthUserResponse",
    "LoginRequest",
    "LoginResponse",
]
