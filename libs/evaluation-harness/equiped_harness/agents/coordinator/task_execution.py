"""Strict JSON normalization and one bounded repair for Coordinator tasks."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any

from equiped_harness.exceptions import (
    AgentExecutionError,
    AgentLLMError,
    error_reference,
)
from equiped_harness.runtime.config import current_execution_config
from equiped_harness.runtime.llm import RunLLMClient
from equiped_harness.runtime.model import CompletionResult, ResponseContract
from equiped_harness.runtime.prompts import AgentPrompt, build_diagnostic_repair_prompt

_LOGGER = logging.getLogger(__name__)
_TRUNCATION_ERROR = "LLM output was truncated"


def _duplicate_key_guard(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _normalize_json_payload(raw: str) -> str:
    """Remove one complete Markdown JSON fence emitted by local models."""
    payload = raw.strip() if isinstance(raw, str) else raw
    if isinstance(payload, str):
        fenced = re.fullmatch(
            r"```[ \t]*(?:json)?\s*(.*?)\s*```",
            payload,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if fenced:
            payload = fenced.group(1).strip()
    return payload


def _decode_json_payload(raw: str) -> Any:
    payload = _normalize_json_payload(raw)
    decoder = json.JSONDecoder(object_pairs_hook=_duplicate_key_guard)
    data, end = decoder.raw_decode(payload)
    # Some models append redundant closing delimiters after a complete value.
    # Never discard another value, prose, or malformed content inside the value.
    if payload[end:].strip().strip("]} \t\r\n"):
        raise ValueError("Extra content after Coordinator JSON response")
    return data


def _parse_json(
    raw: str,
    *,
    allow_bare_results: bool = False,
    require_explanation: bool = False,
    include_summary: bool = False,
) -> dict[str, Any]:
    try:
        data = _decode_json_payload(raw)
    except (TypeError, ValueError) as exc:
        raise AgentExecutionError("Current Coordinator response is not JSON") from exc
    if allow_bare_results and isinstance(data, list):
        data = {"results": data}
    expected_keys = {"results", "explanation"} if require_explanation else {"results"}
    if include_summary:
        expected_keys.add("summary")
    if (
        not isinstance(data, dict)
        or (
            set(data) != expected_keys
            and not (require_explanation and set(data) == {"results"})
        )
        or not isinstance(data["results"], list)
    ):
        raise AgentExecutionError(
            "Current Coordinator response requires only results and summary"
            if include_summary
            else "Current Coordinator response requires results and explanation"
            if require_explanation
            else "Current Coordinator response requires only results"
        )
    if require_explanation:
        data.setdefault("explanation", None)
    return data


def _call_task(
    prompt: AgentPrompt,
    client: RunLLMClient,
    *,
    deadline: float,
    validator: Any | None = None,
    response_budget: int | None = None,
    repair_instruction: str | None = None,
    response_contract: ResponseContract | None = None,
    task_id: str = "unknown",
    include_summary: bool = False,
    capture_prompt: Callable[[AgentPrompt], None] | None = None,
    prompt_budget: int | None = None,
) -> tuple[dict[str, Any], bool, CompletionResult]:
    settings = current_execution_config()
    contract = (
        ResponseContract.json_object()
        if settings.llm_response_mode == "json_object"
        else response_contract or ResponseContract.json_object()
    )
    effective_prompt_budget = min(
        settings.agent_total_prompt_budget_chars,
        prompt_budget
        if prompt_budget is not None
        else settings.agent_total_prompt_budget_chars,
    )
    if len(prompt) > effective_prompt_budget:
        raise AgentExecutionError("Current Coordinator prompt exceeds prompt budget")
    max_new_tokens = min(
        settings.llm_max_new_tokens,
        response_budget if response_budget is not None else settings.llm_max_new_tokens,
    )

    def attempt_deadline() -> float:
        now = time.monotonic()
        if now >= deadline:
            raise AgentExecutionError("Coordinator execution deadline exceeded")
        return min(deadline, now + settings.llm_request_timeout_seconds)

    truncated = False
    try:
        first = client.generate_result(
            prompt,
            temperature=settings.get_agent_temperature("coordinator"),
            max_new_tokens=max_new_tokens,
            deadline=attempt_deadline(),
            response_contract=contract,
        )
    except AgentLLMError as exc:
        if str(exc) != _TRUNCATION_ERROR:
            raise
        truncated = True
        _LOGGER.warning(
            "Coordinator task output truncated; task=%s stage=initial cap=%d",
            task_id,
            max_new_tokens,
        )
        first = None
        validation_error = AgentExecutionError(
            "Current Coordinator response was truncated"
        )
    else:
        validation_error = None
    if first is not None:
        try:
            parsed = _parse_json(
                first.content,
                include_summary=include_summary,
            )
            if validator is not None:
                validator(parsed)
            if capture_prompt is not None:
                capture_prompt(prompt)
            return parsed, False, first
        except AgentExecutionError as exc:
            validation_error = exc
            _LOGGER.warning(
                "Coordinator task validation failed; task=%s stage=initial "
                "reference=%s",
                task_id,
                error_reference(exc),
            )
    if validation_error is not None:
        feedback = str(validation_error)
        instruction_chars = len(repair_instruction) + 2 if repair_instruction else 0
        repair = build_diagnostic_repair_prompt(
            prompt,
            feedback,
            total_budget=effective_prompt_budget - instruction_chars,
        )
        if repair_instruction:
            repair = AgentPrompt(
                system_instruction=(
                    f"{repair.system_instruction}\n\n{repair_instruction}"
                ),
                user_context=repair.user_context,
            )
            if len(repair) > effective_prompt_budget:
                raise AgentExecutionError(
                    "Current Coordinator repair prompt exceeds prompt budget"
                )
        repair_max_new_tokens = (
            min(settings.llm_max_new_tokens, max_new_tokens * 2)
            if truncated
            else max_new_tokens
        )
        try:
            second = client.generate_result(
                repair,
                temperature=settings.get_agent_temperature("coordinator"),
                max_new_tokens=repair_max_new_tokens,
                deadline=attempt_deadline(),
                response_contract=contract,
            )
        except AgentLLMError as exc:
            if str(exc) == _TRUNCATION_ERROR:
                _LOGGER.warning(
                    "Coordinator task output truncated; task=%s stage=repair "
                    "cap=%d repeated=%s",
                    task_id,
                    repair_max_new_tokens,
                    str(truncated).lower(),
                )
            raise
        repaired = None
        try:
            repaired = _parse_json(
                second.content,
                include_summary=include_summary,
            )
            if validator is not None:
                validator(repaired)
        except AgentExecutionError as exc:
            _LOGGER.warning(
                "Coordinator task validation failed; task=%s stage=repair reference=%s",
                task_id,
                error_reference(exc),
            )
            raise
        if capture_prompt is not None:
            capture_prompt(repair)
        return repaired, True, second
