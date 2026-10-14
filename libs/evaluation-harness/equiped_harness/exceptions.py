"""Shared exceptions for evaluation agents."""

from __future__ import annotations

import hashlib


class AgentError(Exception):
    """Base error for agent execution failures."""


class AgentConfigurationError(AgentError):
    """Raised when an agent is misconfigured."""


class AgentRetrievalError(AgentError):
    """Raised when retrieval for an agent cannot complete."""


class AgentLLMError(AgentError):
    """Raised when the local/open-source LLM path fails."""


class AgentExecutionError(AgentError):
    """Raised when an agent cannot finish evaluation."""


class SupervisorExecutionError(AgentError):
    """Raised when the supervisor cannot aggregate results."""


__all__ = [
    "error_reference",
    "AgentConfigurationError",
    "AgentError",
    "AgentExecutionError",
    "AgentLLMError",
    "AgentRetrievalError",
    "SupervisorExecutionError",
]


def error_reference(error: BaseException) -> str:
    return hashlib.sha256(str(error).encode()).hexdigest()[:16]
