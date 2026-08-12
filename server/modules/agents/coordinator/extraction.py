"""Coordinator-local, fact-only curriculum extraction."""

from __future__ import annotations

import json
import time
from typing import Any

from server.core.config import get_settings
from server.core.llm import ResponseContract

from ..runtime.llm import RunLLMClient

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "objectives": {
            "type": "array",
            "maxItems": 100,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"id": {"type": "integer"}, "text": {"type": "string"}},
                "required": ["id", "text"],
            },
        },
        "curriculum_alignment": {
            "type": "array",
            "maxItems": 100,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "objective_id": {"type": "integer"},
                    "is_addressed": {"type": "boolean"},
                    "evidence": {"type": "string"},
                },
                "required": ["objective_id", "is_addressed", "evidence"],
            },
        },
    },
    "required": ["objectives", "curriculum_alignment"],
}


def extract(
    client: RunLLMClient,
    slm_text: str,
    curriculum_text: str,
    *,
    roadmap_note: str = "",
) -> dict[str, Any]:
    """Make the Coordinator's sole model call and validate its facts locally."""
    prompt = f"""Extract facts only. Do not score, infer, or add fields.
Return exactly JSON with objectives and curriculum_alignment. Objective ids must
be unique. For an addressed objective, evidence must be an exact non-empty
quote from the curriculum. If unsure, use false and an empty evidence string.

AUTHORITATIVE SLM TEXT:
{slm_text}

EXACT PRECOMPUTED CURRICULUM CONTEXT:
{curriculum_text}
"""
    if roadmap_note:
        prompt += f"""
SUPPLEMENTARY PROGRAM ROADMAP CONTEXT (ADVISORY ONLY; NOT CURRICULUM EVIDENCE):
{roadmap_note}
Use this only to supplement your review. It must not replace the curriculum,
serve as an alignment target, or be quoted as curriculum evidence.
"""
    settings = get_settings()
    if len(prompt) > settings.agent_total_prompt_budget_chars:
        raise ValueError(
            "Coordinator prompt exceeds agent_total_prompt_budget_chars; "
            "authoritative text cannot be trimmed"
        )
    if settings.llm_response_mode == "json_schema":
        contract = ResponseContract.json_schema(_SCHEMA, name="coordinator_extraction")
    else:
        contract = ResponseContract.json_object()
    deadline = time.monotonic() + float(settings.llm_request_timeout_seconds)
    result = client.generate_result(
        prompt,
        temperature=settings.get_agent_temperature("coordinator"),
        max_new_tokens=settings.llm_max_new_tokens,
        deadline=deadline,
        response_contract=contract,
    )
    try:
        data = json.loads(result.content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid Coordinator extraction JSON") from exc
    if not isinstance(data, dict) or set(data) != {
        "objectives",
        "curriculum_alignment",
    }:
        raise ValueError("invalid Coordinator extraction top-level schema")
    objectives = data["objectives"]
    rows = data["curriculum_alignment"]
    if (
        not isinstance(objectives, list)
        or not isinstance(rows, list)
        or len(objectives) > 100
        or len(rows) > 100
    ):
        raise ValueError("invalid Coordinator extraction bounds")
    ids: set[int] = set()
    for item in objectives:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "text"}
            or type(item["id"]) is not int
            or item["id"] <= 0
            or not isinstance(item["text"], str)
            or not item["text"].strip()
            or item["id"] in ids
        ):
            raise ValueError("invalid Coordinator objective")
        ids.add(item["id"])
    if len(rows) != len(ids):
        raise ValueError("Coordinator alignment must cover each objective")
    seen: set[int] = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"objective_id", "is_addressed", "evidence"}
            or type(row["objective_id"]) is not int
            or row["objective_id"] not in ids
            or row["objective_id"] in seen
            or type(row["is_addressed"]) is not bool
            or not isinstance(row["evidence"], str)
        ):
            raise ValueError("invalid Coordinator alignment row")
        seen.add(row["objective_id"])
        evidence = row["evidence"].strip()
        if row["is_addressed"] and (not evidence or evidence not in curriculum_text):
            raise ValueError("addressed Coordinator evidence is not grounded")
    return data


__all__ = ["extract"]
