"""Fallback-aware provider transport."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from server.core.config import get_settings
from server.core.llm import get_llm_client

from ..exceptions import AgentLLMError

logger = logging.getLogger(__name__)


def _persistent(error: Exception) -> bool:
    text = str(error).lower()
    return any(code in text for code in ("http 429", "http 404", "http 503"))


def error_reference(error: BaseException | Exception) -> str:
    return hashlib.sha256(str(error).encode()).hexdigest()[:16]


def call_llm(
    prompt: str,
    *,
    primary_client: Any | None = None,
    temperature: float | None = None,
    agent_name: str = "agent",
    max_new_tokens: int | None = None,
) -> tuple[str, str]:
    client = primary_client or get_llm_client()
    settings = get_settings()
    temp = temperature if temperature is not None else settings.llm_temperature
    max_tokens = (
        max_new_tokens if max_new_tokens is not None else settings.llm_max_new_tokens
    )
    try:
        return client.generate(
            prompt, temperature=temp, max_new_tokens=max_tokens
        ), getattr(client, "model", "unknown")
    except AgentLLMError:
        raise
    except Exception as exc:
        if primary_client is not None and _persistent(exc):
            fallback = get_llm_client()
            try:
                result = fallback.generate(
                    prompt, temperature=temp, max_new_tokens=max_tokens
                )
                return result, getattr(fallback, "model", "unknown")
            except Exception as fallback_exc:
                logger.info(
                    "[EVAL_MODEL_FALLBACK] agent=%s | category=transport | "
                    "reference=%s",
                    agent_name,
                    error_reference(fallback_exc),
                )
                raise AgentLLMError(
                    f"LLM call failed for {agent_name} "
                    f"(reference: {error_reference(exc)})"
                ) from exc
        raise AgentLLMError(
            f"LLM call failed for {agent_name} (reference: {error_reference(exc)})"
        ) from exc


class FallbackAwareClient:
    """Per-run client adapter that retains model fallback provenance."""

    def __init__(
        self,
        primary_client: Any,
        agent_name: str,
        requested_model: str | None = None,
    ):
        self.primary_client = primary_client
        self.agent_name = agent_name
        self.requested_model = (
            requested_model
            if requested_model is not None
            else getattr(primary_client, "model", None) or "unknown"
        )
        self.actual_model = self.requested_model
        self.fallback_occurred = False

    @property
    def model(self) -> str:
        return self.actual_model

    def generate(
        self, prompt: str, *, temperature: float, max_new_tokens: int
    ) -> str:
        result, actual_model = call_llm(
            prompt,
            primary_client=self.primary_client,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            agent_name=self.agent_name,
        )
        self.actual_model = actual_model
        self.fallback_occurred = self.fallback_occurred or (
            actual_model != self.requested_model
        )
        return result
