"""Backend-only settings and response-contract translation for harness execution."""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from equiped_harness import ExecutionConfig
from equiped_harness.api import ToolConfig
from equiped_harness.runtime.model import CompletionResult, ResponseContract
from equiped_harness.tools.http import PinnedHTTPS

from server.core.exceptions import ConfigurationError
from server.core.llm import ResponseContract as TransportResponseContract


def execution_config_from_settings(settings: Any) -> ExecutionConfig:
    return ExecutionConfig(
        **{
            field.name: getattr(settings, field.name)
            for field in fields(ExecutionConfig)
        }
    )


class HarnessModelClient:
    """Translate neutral contracts; preserve core transport/retry/security behavior."""

    def __init__(self, client: Any) -> None:
        self.client = client

    @property
    def model(self) -> str:
        return getattr(self.client, "model", None) or "unknown"

    def generate_result(
        self,
        prompt: Any,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None = None,
        response_contract: ResponseContract | None = None,
    ) -> CompletionResult:
        if response_contract is not None:
            if not isinstance(response_contract, ResponseContract):
                raise ConfigurationError("Invalid response contract")
            response_contract = TransportResponseContract(
                response_contract.mode,
                response_contract.schema_name,
                response_contract.schema,
            )
        return self.client.generate_result(
            prompt,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            deadline=deadline,
            response_contract=response_contract,
        )


def tool_config_from_settings(settings: Any) -> ToolConfig:
    """Translate host authorization; public tool implementation lives in the library."""
    return ToolConfig(
        enabled=getattr(settings, "itso_verification_enabled", False) is True,
        transport=PinnedHTTPS(),
    )
