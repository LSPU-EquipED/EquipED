"""Lazy SQLAlchemy accessors for the backend runtime."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import DeclarativeBase

from .config import get_settings
from .exceptions import (
    ConfigurationError,
    DependencyUnavailableError,
    InfrastructureUnavailableError,
)


class Base(DeclarativeBase):
    """Shared declarative base for server-side SQLAlchemy models."""


@lru_cache(maxsize=1)
def get_engine() -> Any:
    """Create the SQLAlchemy engine only when database access is requested."""

    settings = get_settings()
    if not settings.database_url:
        raise ConfigurationError("DATABASE_URL is not configured")

    try:
        from sqlalchemy import create_engine
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise DependencyUnavailableError("SQLAlchemy is not installed") from exc

    try:
        return create_engine(
            settings.database_url,
            echo=settings.database_echo,
            future=True,
            pool_pre_ping=True,
        )
    except Exception as exc:  # pragma: no cover - driver/init guard
        raise InfrastructureUnavailableError(
            "SQLAlchemy engine could not be created"
        ) from exc


@lru_cache(maxsize=1)
def get_session_factory() -> Any:
    """Create a cached SQLAlchemy session factory."""

    try:
        from sqlalchemy.orm import sessionmaker
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise DependencyUnavailableError("SQLAlchemy ORM is not installed") from exc

    try:
        return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    except Exception as exc:  # pragma: no cover - session init guard
        raise InfrastructureUnavailableError(
            "SQLAlchemy session factory could not be created"
        ) from exc


def get_db_session() -> Iterator[Any]:
    """Yield a database session with deterministic cleanup."""

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


__all__ = ["Base", "get_engine", "get_session_factory", "get_db_session"]
