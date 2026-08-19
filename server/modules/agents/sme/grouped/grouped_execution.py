"""LLM transport for one SME grouped-scoring call, with repair-once on a
parse failure. Mirrors ``itso/execution.py``'s repair shape.
"""

from __future__ import annotations

import time

from server.core.config import get_settings
from server.core.llm import ResponseContract

from ...contracts import CriterionScore
from ...exceptions import AgentExecutionError
from ...runtime.llm import RunLLMClient
from .grouped_prompt import build_group_prompt
from .grouped_response import (
    build_group_response_schema,
    group_criterion_scores,
    parse_group_response,
)

_REPAIR_SUFFIX = (
    "\n\nVALIDATOR_FAILURE category=SME_GROUP_INVALID path=criterion_scores. "
    "Regenerate ONLY the complete JSON response; do not include commentary."
)


def execute_group(
    group: str,
    codes: tuple[str, ...],
    titles: dict[str, str],
    descriptions: dict[str, str],
    client: RunLLMClient,
    full_text: str,
    *,
    prompt_preamble: str | None = None,
) -> tuple[tuple[CriterionScore, ...], str]:
    settings = get_settings()
    prompt = build_group_prompt(
        group, codes, titles, descriptions, full_text, prompt_preamble=prompt_preamble
    )
    if settings.llm_response_mode == "json_schema":
        contract = ResponseContract.json_schema(
            build_group_response_schema(codes, titles),
            name=f"sme_group_{group}",
        )
    else:
        contract = ResponseContract.json_object()
    temperature = settings.get_agent_temperature("sme")
    deadline = time.monotonic() + float(
        getattr(settings, "llm_request_timeout_seconds", 120)
    )
    completion = client.generate_result(
        prompt,
        temperature=temperature,
        max_new_tokens=settings.llm_max_new_tokens,
        deadline=deadline,
        response_contract=contract,
    )
    try:
        parsed = parse_group_response(completion.content, codes, titles)
    except AgentExecutionError:
        repaired = client.generate_result(
            prompt + _REPAIR_SUFFIX,
            temperature=temperature,
            max_new_tokens=settings.llm_max_new_tokens,
            deadline=deadline,
            response_contract=contract,
        )
        parsed = parse_group_response(repaired.content, codes, titles)
    scores = group_criterion_scores(parsed, codes, titles)
    return scores, prompt


__all__ = ["execute_group"]
