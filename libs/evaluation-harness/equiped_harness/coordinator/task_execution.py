"""Strict JSON normalization and one bounded repair for Coordinator tasks."""

from __future__ import annotations

import json
import re
from typing import Any

from equiped_harness.config import current_execution_config
from equiped_harness.exceptions import AgentExecutionError, AgentLLMError
from equiped_harness.runtime.llm import RunLLMClient
from equiped_harness.runtime.prompts import AgentPrompt, build_diagnostic_repair_prompt
from equiped_harness.transport import CompletionResult, ResponseContract


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
    return json.loads(
        _normalize_json_payload(raw), object_pairs_hook=_duplicate_key_guard
    )


def _parse_json(raw: str, *, allow_bare_results: bool = False) -> dict[str, Any]:
    try:
        data = _decode_json_payload(raw)
    except (TypeError, ValueError) as exc:
        raise AgentExecutionError("Current Coordinator response is not JSON") from exc
    if allow_bare_results and isinstance(data, list):
        data = {"results": data}
    if (
        not isinstance(data, dict)
        or set(data) != {"results"}
        or not isinstance(data["results"], list)
    ):
        raise AgentExecutionError("Current Coordinator response requires only results")
    return data


def _call_task(
    prompt: AgentPrompt,
    client: RunLLMClient,
    *,
    deadline: float,
    validator: Any | None = None,
    response_budget: int | None = None,
    repair_instruction: str | None = None,
    allow_bare_results: bool = False,
    allow_legacy: bool = True,
    response_contract: ResponseContract | None = None,
) -> tuple[dict[str, Any], bool, CompletionResult]:
    settings = current_execution_config()
    contract = response_contract or ResponseContract.json_object()
    max_new_tokens = min(
        settings.llm_max_new_tokens,
        response_budget if response_budget is not None else settings.llm_max_new_tokens,
    )
    try:
        first = client.generate_result(
            prompt,
            temperature=settings.get_agent_temperature("coordinator"),
            max_new_tokens=max_new_tokens,
            deadline=deadline,
            response_contract=contract,
        )
    except AgentLLMError as exc:
        if str(exc) != "LLM output was truncated":
            raise
        first = None
        validation_error = AgentExecutionError(
            "Current Coordinator response was truncated"
        )
    else:
        validation_error = None
    if first is not None:
        try:
            legacy = _decode_json_payload(first.content)
            if (
                allow_legacy
                and isinstance(legacy, dict)
                and set(legacy)
                == {
                    "summary",
                    "criterion_measurements",
                }
            ):
                return legacy, False, first
        except (TypeError, ValueError):
            pass
        try:
            parsed = _parse_json(first.content, allow_bare_results=allow_bare_results)
            if validator is not None:
                validator(parsed)
            return parsed, False, first
        except AgentExecutionError as exc:
            validation_error = exc
    if validation_error is not None:
        repair = build_diagnostic_repair_prompt(
            prompt,
            validation_error,
            total_budget=settings.agent_total_prompt_budget_chars,
        )
        if repair_instruction:
            repair = AgentPrompt(
                system_instruction=(
                    f"{repair.system_instruction}\n\n{repair_instruction}"
                ),
                user_context=repair.user_context,
            )
            if len(repair) > settings.agent_total_prompt_budget_chars:
                raise AgentExecutionError(
                    "Current Coordinator repair prompt exceeds prompt budget"
                )
        second = client.generate_result(
            repair,
            temperature=settings.get_agent_temperature("coordinator"),
            max_new_tokens=max_new_tokens,
            deadline=deadline,
            response_contract=contract,
        )
        repaired = _parse_json(second.content, allow_bare_results=allow_bare_results)
        if validator is not None:
            validator(repaired)
        return repaired, True, second
