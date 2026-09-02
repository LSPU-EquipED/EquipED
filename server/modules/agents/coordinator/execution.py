"""Envelope LLM transport and repair execution for Coordinator.

Copy-adapted from ``server/modules/agents/sme/execution.py``. Differences:
the ``curriculum_context`` positional, the ``agent_total_prompt_budget_chars``
budget, the ``coordinator`` temperature/schema names, and the curriculum-context
argument threaded into ``parse_and_validate_envelope_response``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from server.core.config import get_settings
from server.core.llm import ResponseContract
from server.modules.rubrics.contracts import CriterionDefinition

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError, AgentLLMError
from ..runtime.llm import RunLLMClient, error_reference
from .prompt import REPAIR_SUFFIX, build_envelope_prompt_and_source
from .response import (
    build_envelope_schema,
    parse_and_validate_envelope_response,
)
from .scoring import score_envelope

logger = logging.getLogger(__name__)


def execute_envelope(
    envelope_idx: int,
    criteria: tuple[CriterionDefinition, ...],
    client: RunLLMClient,
    canonical_source_text: str,
    curriculum_context: str,
    *,
    prompt_preamble: str | None = None,
    temperature: float | None = None,
    deadline: float | None = None,
) -> tuple[tuple[CriterionScore, ...], str, dict[str, Any], bool]:
    """Execute one Coordinator envelope call with one repair on validation failure."""
    settings = get_settings()
    prompt_budget = settings.agent_total_prompt_budget_chars

    prompt, source_packet = build_envelope_prompt_and_source(
        criteria,
        canonical_source_text=canonical_source_text,
        curriculum_context=curriculum_context,
        prompt_budget=prompt_budget,
        prompt_preamble=prompt_preamble,
    )

    if getattr(settings, "llm_response_mode", "json_object") == "json_schema":
        schema = build_envelope_schema(criteria)
        contract = ResponseContract.json_schema(
            schema, name=f"coordinator_envelope_{envelope_idx}"
        )
    else:
        contract = ResponseContract.json_object()

    temp = (
        temperature
        if temperature is not None
        else settings.get_agent_temperature("coordinator")
    )
    req_deadline = deadline or (
        time.monotonic() + float(getattr(settings, "llm_request_timeout_seconds", 120))
    )

    validation_error: AgentExecutionError | None = None
    parsed: dict[str, Any] | None = None
    try:
        completion = client.generate_result(
            prompt,
            temperature=temp,
            max_new_tokens=settings.llm_max_new_tokens,
            deadline=req_deadline,
            response_contract=contract,
        )
        try:
            parsed = parse_and_validate_envelope_response(
                completion.content, criteria, source_packet, curriculum_context
            )
        except AgentExecutionError as exc:
            validation_error = exc
    except AgentLLMError as exc:
        if str(exc) != "LLM output was truncated":
            raise
        validation_error = AgentExecutionError("Coordinator response was truncated")

    repair_occurred = False
    if validation_error is not None:
        logger.info(
            "[COORDINATOR_REPAIR] envelope=%d category=%s reference=%s",
            envelope_idx,
            type(validation_error).__name__,
            error_reference(validation_error),
        )
        repair_prompt = prompt + REPAIR_SUFFIX
        if len(repair_prompt) > prompt_budget:
            raise AgentExecutionError(
                "Coordinator repair prompt exceeds total prompt budget"
            ) from validation_error

        repaired_completion = client.generate_result(
            repair_prompt,
            temperature=temp,
            max_new_tokens=settings.llm_max_new_tokens,
            deadline=req_deadline,
            response_contract=contract,
        )
        parsed = parse_and_validate_envelope_response(
            repaired_completion.content, criteria, source_packet, curriculum_context
        )
        repair_occurred = True

    if parsed is None:
        raise AgentExecutionError(
            "Coordinator response validation produced no result"
        )
    scores = score_envelope(criteria, parsed)
    return scores, prompt, parsed, repair_occurred


__all__ = ["execute_envelope"]
