"""Environment-backed settings for the server core layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from .exceptions import ConfigurationError


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str) -> tuple[str, ...]:
    value = _env(name)
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "EquipEd"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: tuple[str, ...] = ()
    cors_allow_credentials: bool = True

    database_url: str | None = None
    database_echo: bool = False

    session_cookie_name: str = "equiped_session"
    session_ttl_hours: int = 24
    bootstrap_admin_email: str | None = None
    bootstrap_admin_name: str | None = None
    bootstrap_admin_password: str | None = None

    chroma_persist_directory: str = "chroma_data"
    chroma_host: str | None = None
    chroma_port: int | None = None
    chroma_ssl: bool = False

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5"

    embedding_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def chroma_configured(self) -> bool:
        if self.chroma_host:
            return self.chroma_port is not None
        return bool(self.chroma_persist_directory)

    @property
    def llm_configured(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def embedding_configured(self) -> bool:
        return bool(self.embedding_model_name)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load process settings once and reuse them as a singleton."""
    from dotenv import load_dotenv

    load_dotenv()

    chroma_port = _env("CHROMA_PORT")
    if chroma_port:
        try:
            parsed_chroma_port = int(chroma_port)
        except ValueError as exc:
            raise ConfigurationError("CHROMA_PORT must be a valid integer") from exc
    else:
        parsed_chroma_port = None

    session_ttl_hours = _env("SESSION_TTL_HOURS", "24")
    try:
        parsed_session_ttl_hours = int(session_ttl_hours or "24")
    except ValueError as exc:
        raise ConfigurationError("SESSION_TTL_HOURS must be a valid integer") from exc

    settings = Settings(
        app_name=_env("APP_NAME", "EquipEd") or "EquipEd",
        app_version=_env("APP_VERSION", "0.1.0") or "0.1.0",
        environment=_env("APP_ENV", "development") or "development",
        api_prefix=_env("API_PREFIX", "/api/v1") or "/api/v1",
        cors_origins=_csv_env("CORS_ORIGINS"),
        cors_allow_credentials=_bool_env("CORS_ALLOW_CREDENTIALS", True),
        database_url=_env("DATABASE_URL"),
        database_echo=_bool_env("DATABASE_ECHO", False),
        session_cookie_name=_env("SESSION_COOKIE_NAME", "equiped_session")
        or "equiped_session",
        session_ttl_hours=parsed_session_ttl_hours,
        bootstrap_admin_email=_env("BOOTSTRAP_ADMIN_EMAIL"),
        bootstrap_admin_name=_env("BOOTSTRAP_ADMIN_NAME"),
        bootstrap_admin_password=_env("BOOTSTRAP_ADMIN_PASSWORD"),
        chroma_persist_directory=_env("CHROMA_PERSIST_DIRECTORY", "chroma_data")
        or "chroma_data",
        chroma_host=_env("CHROMA_HOST"),
        chroma_port=parsed_chroma_port,
        chroma_ssl=_bool_env("CHROMA_SSL", False),
        anthropic_api_key=_env("ANTHROPIC_API_KEY"),
        anthropic_model=_env("ANTHROPIC_MODEL", "claude-haiku-4-5")
        or "claude-haiku-4-5",
        embedding_model_name=_env(
            "EMBEDDING_MODEL_NAME",
            "paraphrase-multilingual-MiniLM-L12-v2",
        )
        or "paraphrase-multilingual-MiniLM-L12-v2",
    )

    if settings.cors_allow_credentials and "*" in settings.cors_origins:
        raise ConfigurationError(
            "CORS_ORIGINS cannot include '*' when credentials are enabled"
        )

    bootstrap_values = (
        settings.bootstrap_admin_email,
        settings.bootstrap_admin_name,
        settings.bootstrap_admin_password,
    )
    if any(bootstrap_values) and not all(bootstrap_values):
        raise ConfigurationError(
            "BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_NAME, and "
            "BOOTSTRAP_ADMIN_PASSWORD must be set together"
        )

    return settings


__all__ = ["Settings", "get_settings"]
