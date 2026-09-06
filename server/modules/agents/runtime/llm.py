"""Agent transport adapter with per-run completion telemetry."""

from __future__ import annotations

import hashlib
import inspect
import threading
from typing import Any

from server.core.config import get_settings
from server.core.llm import (
    CompletionResult,
    ResponseContract,
    get_llm_client,
    parse_json_payload,
)

from ..exceptions import AgentLLMError


def error_reference(error: BaseException | Exception) -> str:
    return hashlib.sha256(str(error).encode()).hexdigest()[:16]


def call_llm(
    prompt: str,
    *,
    primary_client: Any | None = None,
    temperature: float | None = None,
    agent_name: str = "agent",
    max_new_tokens: int | None = None,
    deadline: float | None = None,
    response_contract: ResponseContract | None = None,
) -> CompletionResult:
    client = primary_client if primary_client is not None else get_llm_client()
    settings = get_settings()
    temp = temperature if temperature is not None else settings.llm_temperature
    max_tokens = (
        max_new_tokens if max_new_tokens is not None else settings.llm_max_new_tokens
    )
    try:
        adapter = (
            client
            if isinstance(client, RunLLMClient)
            else RunLLMClient(client, agent_name)
        )
        return adapter.generate_result(
            prompt,
            temperature=temp,
            max_new_tokens=max_tokens,
            deadline=deadline,
            response_contract=response_contract,
        )
    except AgentLLMError:
        raise
    except Exception as exc:
        raise AgentLLMError(
            f"LLM call failed for {agent_name} (reference: {error_reference(exc)})"
        ) from exc


class RunLLMClient:
    """Per-run adapter with bounded transport telemetry (no fallback)."""

    def __init__(
        self,
        primary_client: Any,
        agent_name: str,
        requested_model: str | None = None,
        default_response_contract: ResponseContract | None = None,
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
        self.default_response_contract = default_response_contract
        self._lock = threading.Lock()
        self.telemetry = {
            "call_count": 0,
            "attempt_count": 0,
            "cap_hit_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "usage_available": False,
            "wall_seconds": 0.0,
            "provider_seconds": 0.0,
            "requested_max_tokens": 0,
            "finish_reason_counts": {},
            "grouped_calls": 0,
            "fallback_calls": 0,
            "response_format_downgraded": False,
        }

    @property
    def model(self) -> str:
        return self.actual_model

    def _record_result(self, result: CompletionResult) -> CompletionResult:
        with self._lock:
            self.actual_model = str(result.served_model)[:128]
            self.telemetry["attempt_count"] += min(max(result.attempts, 0), 32)
            self.telemetry["wall_seconds"] += min(
                max(result.wall_seconds or 0.0, 0.0), 3600.0
            )
            self.telemetry["provider_seconds"] += min(
                max(result.provider_seconds or 0.0, 0.0), 3600.0
            )
            self.telemetry["requested_max_tokens"] += min(
                max(result.requested_max_tokens or 0, 0), 10_000_000
            )
            if result.finish_reason:
                counts = self.telemetry["finish_reason_counts"]
                key = str(result.finish_reason)[:32]
                counts[key] = min(counts.get(key, 0) + 1, 1000)
            if result.total_tokens is not None:
                self.telemetry["usage_available"] = True
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    value = getattr(result, key)
                    if value is not None:
                        self.telemetry[key] += min(max(value, 0), 10_000_000)
            if result.response_format_downgraded:
                self.telemetry["response_format_downgraded"] = True
            truncated = result.finish_reason == "length" or result.output_cap_hit
            if truncated:
                self.telemetry["cap_hit_count"] += 1
        if truncated:
            raise AgentLLMError("LLM output was truncated")
        return result

    def generate_result(
        self,
        prompt: Any,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None = None,
        response_contract: ResponseContract | None = None,
    ) -> CompletionResult:
        with self._lock:
            self.telemetry["call_count"] += 1
        response_contract = response_contract or self.default_response_contract
        try:
            if hasattr(self.primary_client, "generate_result"):
                generate_result = self.primary_client.generate_result
                inspect.signature(generate_result).bind(
                    prompt,
                    temperature=temperature,
                    max_new_tokens=max_new_tokens,
                    deadline=deadline,
                    response_contract=response_contract,
                )
                result = generate_result(
                    prompt,
                    temperature=temperature,
                    max_new_tokens=max_new_tokens,
                    deadline=deadline,
                    response_contract=response_contract,
                )
            else:
                if response_contract is not None:
                    raise AgentLLMError(
                        "LLM client does not support response contracts"
                    )
                result = self.primary_client.generate(
                    prompt, temperature=temperature, max_new_tokens=max_new_tokens
                )
        except AgentLLMError:
            raise
        except Exception as exc:
            raise AgentLLMError(
                f"LLM call failed for {self.agent_name} "
                f"(reference: {error_reference(exc)})"
            ) from exc
        if isinstance(result, str):
            result = CompletionResult(content=result, served_model=self.requested_model)
        if not isinstance(result, CompletionResult):
            raise AgentLLMError("LLM client returned an invalid completion result")
        return self._record_result(result)

    def generate(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None = None,
        response_contract: ResponseContract | None = None,
    ) -> str:
        return self.generate_result(
            prompt,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            deadline=deadline,
            response_contract=response_contract,
        ).content


__all__ = ["call_llm", "RunLLMClient", "error_reference", "parse_json_payload"]
