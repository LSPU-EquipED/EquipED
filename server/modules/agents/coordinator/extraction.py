"""Coordinator-local, fact-only curriculum extraction."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from server.core.config import get_settings
from server.core.llm import ResponseContract

from ..runtime.llm import RunLLMClient, parse_json_payload

logger = logging.getLogger(__name__)

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
Extract learning objectives from the AUTHORITATIVE SLM TEXT ONLY.
Evaluate alignment against EXACT PRECOMPUTED CURRICULUM CONTEXT.

Output must be a single JSON object with EXACTLY this shape:
{{
  "objectives": [
    {{"id": 1, "text": "exact objective text from SLM"}}
  ],
  "curriculum_alignment": [
    {{
      "objective_id": 1,
      "is_addressed": true,
      "evidence": "exact verbatim quote from curriculum context"
    }}
  ]
}}

STRICT RULES:
1. "objectives" and "curriculum_alignment" must be top-level arrays of the
   same length with identical positive integer IDs.
2. Each objective in "objectives" must have ONLY "id" (positive integer)
   and "text" (non-empty string). Do NOT nest alignment or evidence under
   objectives.
3. Each row in "curriculum_alignment" must have ONLY "objective_id"
   (positive integer), "is_addressed" (boolean), and "evidence" (string).
4. Do NOT output rows per curriculum outcome. Output exactly ONE alignment
   row for each SLM objective.
5. If is_addressed is true, evidence must be exactly one verbatim excerpt
   from the EXACT PRECOMPUTED CURRICULUM CONTEXT.
6. If is_addressed is false (or unsure), evidence must be an empty string "".
7. Do not include commentary or extra fields.

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
    logger.info(
        "[EVAL_TIMING] agent=coordinator | phase=prompt_preflight | "
        "process_id=%d | slm_chars=%d | curriculum_chars=%d | "
        "roadmap_chars=%d | prompt_chars=%d | budget_chars=%d",
        os.getpid(),
        len(slm_text),
        len(curriculum_text),
        len(roadmap_note),
        len(prompt),
        settings.agent_total_prompt_budget_chars,
    )
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
        data = parse_json_payload(result.content)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid Coordinator extraction JSON") from exc
    if not isinstance(data, dict) or set(data) != {
        "objectives",
        "curriculum_alignment",
    }:
        raise ValueError("invalid Coordinator extraction top-level schema")
    raw_objectives = data["objectives"]
    rows = data["curriculum_alignment"]
    if (
        not isinstance(raw_objectives, list)
        or not isinstance(rows, list)
        or len(raw_objectives) > 100
        or len(rows) > 100
    ):
        raise ValueError("invalid Coordinator extraction bounds")

    _ALIAS_KEYS = {"objective_id", "objective", "curriculum_alignment", "evidence"}
    all_canonical = all(
        isinstance(item, dict) and set(item) == {"id", "text"}
        for item in raw_objectives
    )
    all_alias = (
        not all_canonical
        and len(raw_objectives) > 0
        and all(
            isinstance(item, dict) and set(item) == _ALIAS_KEYS
            for item in raw_objectives
        )
    )

    if all_canonical:
        objectives = raw_objectives
    elif all_alias:
        objectives = [
            {"id": item["objective_id"], "text": item["objective"]}
            for item in raw_objectives
        ]
        logger.info(
            "[COORDINATOR_NORMALIZATION] normalized_alias_objectives count=%d",
            len(objectives),
        )
    else:
        raise ValueError("invalid Coordinator objectives structure")

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
        if not row["is_addressed"] and evidence:
            raise ValueError(
                "unaddressed Coordinator alignment must have empty evidence"
            )
    return {"objectives": objectives, "curriculum_alignment": rows}


__all__ = ["extract"]
