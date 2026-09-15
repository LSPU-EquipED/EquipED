"""Lazy sentence-transformer embedding model singleton."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .config import get_settings
from .exceptions import DependencyUnavailableError, InfrastructureUnavailableError


@lru_cache(maxsize=1)
def get_embedding_model() -> Any:
    """Create the embedding model only when it is explicitly requested."""

    settings = get_settings()

    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise DependencyUnavailableError(
            "sentence-transformers is not installed"
        ) from exc

    try:
        return SentenceTransformer(settings.embedding_model_name)
    except Exception as exc:  # pragma: no cover - model init guard
        raise InfrastructureUnavailableError(
            "Embedding model could not be created"
        ) from exc


__all__ = ["get_embedding_model"]
