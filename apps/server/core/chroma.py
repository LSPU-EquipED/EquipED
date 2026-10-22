"""Lazy ChromaDB client singleton."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .config import get_settings
from .exceptions import (
    ConfigurationError,
    DependencyUnavailableError,
    InfrastructureUnavailableError,
)


@lru_cache(maxsize=1)
def get_chroma_client() -> Any:
    """Create the Chroma client only when a caller asks for it."""

    settings = get_settings()

    try:
        import chromadb
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise DependencyUnavailableError("ChromaDB is not installed") from exc

    cloud_host = (settings.chroma_host or "").strip().lower()
    cloud_requested = bool(
        settings.chroma_api_key
        or settings.chroma_tenant
        or settings.chroma_database
        or cloud_host == "api.trychroma.com"
    )
    if cloud_requested:
        if settings.chroma_host and cloud_host != "api.trychroma.com":
            raise ConfigurationError(
                "CHROMA_HOST must be api.trychroma.com when using Chroma Cloud"
            )
        missing = [
            name
            for name, value in (
                ("CHROMA_API_KEY", settings.chroma_api_key),
                ("CHROMA_TENANT", settings.chroma_tenant),
                ("CHROMA_DATABASE", settings.chroma_database),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError(
                "Chroma Cloud configuration is incomplete; set " + ", ".join(missing)
            )
        try:
            return chromadb.CloudClient(
                api_key=settings.chroma_api_key,
                tenant=settings.chroma_tenant,
                database=settings.chroma_database,
            )
        except Exception:
            # Chroma exceptions may include the API key in their details.
            pass
        raise InfrastructureUnavailableError(
            "Chroma Cloud client could not be created"
        ) from None

    if settings.chroma_host:
        if settings.chroma_port is None:
            raise ConfigurationError("CHROMA_PORT is required when CHROMA_HOST is set")
        try:
            return chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                ssl=settings.chroma_ssl,
            )
        except Exception:  # pragma: no cover - client init guard
            raise InfrastructureUnavailableError(
                "Chroma HTTP client could not be created"
            ) from None

    try:
        return chromadb.PersistentClient(path=settings.chroma_persist_directory)
    except Exception:  # pragma: no cover - client init guard
        raise InfrastructureUnavailableError(
            "Chroma persistent client could not be created"
        ) from None


__all__ = ["get_chroma_client"]
