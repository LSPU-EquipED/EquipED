"""Pydantic schemas for the authentication module."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import UserRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)


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


class BootstrapAdminResponse(BaseModel):
    created: bool
    email: str | None = None


__all__ = [
    "AuthStateResponse",
    "AuthUserResponse",
    "BootstrapAdminResponse",
    "LoginRequest",
    "LoginResponse",
]
