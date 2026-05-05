"""Lazy Anthropic client singleton."""

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
def get_llm_client() -> Any:
    """Create the LLM client only when it is explicitly requested."""

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ConfigurationError("ANTHROPIC_API_KEY is not configured")

    try:
        from anthropic import Anthropic
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise DependencyUnavailableError("Anthropic SDK is not installed") from exc

    try:
        return Anthropic(api_key=settings.anthropic_api_key)
    except Exception as exc:  # pragma: no cover - client init guard
        raise InfrastructureUnavailableError(
            "Anthropic client could not be created"
        ) from exc


def get_llm_model_name() -> str:
    """Expose the configured default model name for downstream callers."""

    return get_settings().anthropic_model


__all__ = ["get_llm_client", "get_llm_model_name"]
