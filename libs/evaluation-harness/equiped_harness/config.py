"""Immutable execution controls, with no environment or backend resolution."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, fields


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    llm_temperature: float = 0.2
    llm_temperature_itso: float = 0.0
    llm_max_new_tokens: int = 4096
    llm_request_timeout_seconds: float = 120
    llm_response_mode: str = "json_object"
    agent_max_chunks: int = 12
    agent_max_excerpt_chars: int = 800
    agent_prompt_budget_chars: int = 5000
    agent_small_doc_threshold: int = 6
    agent_total_prompt_budget_chars: int = 32000
    sme_total_prompt_budget_chars: int = 15000

    def __post_init__(self) -> None:
        for name in ("llm_temperature", "llm_temperature_itso"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not math.isfinite(value)
            ):
                raise ValueError(f"Invalid {name}")
        # Global temperature and packing caps have no backend upper bound.
        # Keep this seam compatible with legitimate existing Settings values.
        if not 0 <= self.llm_temperature_itso < 1:
            raise ValueError("Invalid llm_temperature_itso")
        if self.llm_response_mode not in {"json_object", "json_schema"}:
            raise ValueError("Invalid llm_response_mode")
        for field in fields(self):
            if field.name in {
                "llm_temperature",
                "llm_temperature_itso",
                "llm_response_mode",
            }:
                continue
            value = getattr(self, field.name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 1
            ):
                raise ValueError(f"Invalid {field.name}")
            if field.name != "llm_request_timeout_seconds" and not isinstance(
                value, int
            ):
                raise ValueError(f"Invalid {field.name}")
        if self.llm_request_timeout_seconds > 3600:
            raise ValueError("Invalid llm_request_timeout_seconds")
        if self.llm_max_new_tokens > 32768:
            raise ValueError("Invalid llm_max_new_tokens")

    def get_agent_temperature(self, agent_name: str) -> float:
        return (
            self.llm_temperature_itso if agent_name == "itso" else self.llm_temperature
        )


_CONFIG: ContextVar[ExecutionConfig] = ContextVar(
    "harness_execution_config", default=ExecutionConfig()
)


def current_execution_config() -> ExecutionConfig:
    """Pure helper defaults; production calls evaluate with explicit config."""
    return _CONFIG.get()


@contextmanager
def execution_scope(config: ExecutionConfig) -> Iterator[None]:
    """Scope only immutable execution controls; always restore on success/failure."""
    if not isinstance(config, ExecutionConfig):
        raise TypeError("config must be ExecutionConfig")
    token = _CONFIG.set(config)
    try:
        yield
    finally:
        _CONFIG.reset(token)
