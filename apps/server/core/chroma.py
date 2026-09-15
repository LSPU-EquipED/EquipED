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

    if settings.chroma_host:
        if settings.chroma_port is None:
            raise ConfigurationError("CHROMA_PORT is required when CHROMA_HOST is set")
        try:
            return chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                ssl=settings.chroma_ssl,
            )
        except Exception as exc:  # pragma: no cover - client init guard
            raise InfrastructureUnavailableError(
                "Chroma HTTP client could not be created"
            ) from exc

    try:
        return chromadb.PersistentClient(path=settings.chroma_persist_directory)
    except Exception as exc:  # pragma: no cover - client init guard
        raise InfrastructureUnavailableError(
            "Chroma persistent client could not be created"
        ) from exc


__all__ = ["get_chroma_client"]
