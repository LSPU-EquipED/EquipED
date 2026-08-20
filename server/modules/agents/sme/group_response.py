"""Response schema and parsing for SME's grouped LLM-scoring calls.

Mirrors ``itso/response.py`` exactly, minus chunk-citation handling -- SME
scores from the full canonical SLM text (see
``EngineScoredAgent._resolve_full_text``), not retrieved chunks, so there is
no known-chunk-id set to validate citations against.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError

SME_TEXT_MAX = 2000

_CRITERION_ITEM_KEYS = {
    "criterion_id",
    "criterion_title",
    "score",
    "justification",
    "evidence",
}


def _failure(category: str, value: Any) -> AgentExecutionError:
    reference = hashlib.sha256(str(value).encode()).hexdigest()[:16]
    return AgentExecutionError(f"{category} (reference: {reference})")


_CATEGORY_HINTS: dict[str, str] = {
    "SMEGroupResponseTypeError": (
        "Your response must be plain text containing JSON, not another type."
    ),
    "SMEGroupInvalidJSON": (
        "Your response was not valid JSON. Return a single JSON object with "
        "no commentary before or after it."
    ),
    "SMEGroupInvalidResponse": (
        'The top-level JSON object must have exactly two keys: "summary" '
        '(a string) and "criterion_scores" (an array).'
    ),
    "SMEGroupInvalidCriterionScores": (
        '"criterion_scores" must be an array with exactly one entry per '
        "criterion, in the exact order listed."
    ),
    "SMEGroupInvalidCriterion": (
        "Each criterion_scores entry must be an object with exactly these "
        "keys: criterion_id, criterion_title, score, justification, "
        "evidence -- and criterion_id must match the expected code for its "
        "position."
    ),
    "SMEGroupInvalidCriterionTitle": (
        '"criterion_title" must exactly match the title given for that '
        "criterion_id."
    ),
    "SMEGroupInvalidScore": (
        '"score" must be an integer from 1 to 4 (not a string or boolean).'
    ),
    "SMEGroupInvalidJustification": '"justification" must be a non-empty string.',
    "SMEGroupInvalidEvidence": (
        '"evidence" must be an array of non-empty strings (max 8 items).'
    ),
}


def repair_hint(exc: AgentExecutionError) -> str:
    """Human-readable explanation of what was wrong, for the retry prompt."""
    category = str(exc).split(" (reference:", 1)[0]
    return _CATEGORY_HINTS.get(
        category, "Your response did not match the required JSON shape."
    )


def build_group_response_schema(
    codes: tuple[str, ...], titles: dict[str, str]
) -> dict[str, Any]:
    def _entry(code: str) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "criterion_id",
                "criterion_title",
                "score",
                "justification",
                "evidence",
            ],
            "properties": {
                "criterion_id": {"const": code},
                "criterion_title": {"const": titles[code]},
                "score": {"type": "integer", "minimum": 1, "maximum": 4},
                "justification": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": SME_TEXT_MAX,
                },
                "evidence": {
                    "type": "array",
                    "maxItems": 8,
                    "items": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": SME_TEXT_MAX,
                    },
                },
            },
        }

    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "criterion_scores"],
        "properties": {
            "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
            "criterion_scores": {
                "type": "array",
                "minItems": len(codes),
                "maxItems": len(codes),
                "prefixItems": [_entry(code) for code in codes],
                "items": _entry(codes[0]) if codes else {"type": "object"},
            },
        },
    }


def parse_group_response(
    raw: str, codes: tuple[str, ...], titles: dict[str, str]
) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise _failure("SMEGroupResponseTypeError", type(raw).__name__)
    payload = raw.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", payload, flags=re.I | re.S)
    if match:
        payload = match.group(1).strip()
    elif not payload.startswith("{"):
        raise _failure("SMEGroupInvalidJSON", raw)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise _failure("SMEGroupInvalidJSON", raw) from exc
    if (
        not isinstance(parsed, dict)
        or set(parsed) != {"summary", "criterion_scores"}
        or not isinstance(parsed.get("summary"), str)
        or not 1 <= len(parsed["summary"]) <= 2000
    ):
        raise _failure("SMEGroupInvalidResponse", type(parsed).__name__)
    group_criterion_scores(parsed, codes, titles)
    return parsed


def group_criterion_scores(
    parsed: dict[str, Any], codes: tuple[str, ...], titles: dict[str, str]
) -> tuple[CriterionScore, ...]:
    entries = parsed.get("criterion_scores")
    if not isinstance(entries, list) or len(entries) != len(codes):
        raise _failure("SMEGroupInvalidCriterionScores", "shape")
    seen: set[str] = set()
    result: list[CriterionScore] = []
    for index, (item, expected_code) in enumerate(zip(entries, codes, strict=True)):
        if (
            not isinstance(item, dict)
            or item.get("criterion_id") != expected_code
            or expected_code in seen
            or set(item) != _CRITERION_ITEM_KEYS
        ):
            raise _failure("SMEGroupInvalidCriterion", index)
        if item.get("criterion_title") != titles.get(expected_code):
            raise _failure("SMEGroupInvalidCriterionTitle", index)
        seen.add(expected_code)
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 4:
            raise _failure("SMEGroupInvalidScore", index)
        justification = item.get("justification")
        if (
            not isinstance(justification, str)
            or not justification
            or len(justification) > SME_TEXT_MAX
        ):
            raise _failure("SMEGroupInvalidJustification", index)
        evidence = item.get("evidence")
        if (
            not isinstance(evidence, list)
            or len(evidence) > 8
            or any(
                not isinstance(e, str) or not e or len(e) > SME_TEXT_MAX
                for e in evidence
            )
        ):
            raise _failure("SMEGroupInvalidEvidence", index)
        result.append(
            CriterionScore(
                criterion_id=expected_code,
                criterion_title=item["criterion_title"],
                score=score,
                justification=justification,
                chunk_ids=(),
                evidence=tuple(evidence),
            )
        )
    return tuple(result)


def canonical_group_response_snapshot(
    parsed: dict[str, Any], codes: tuple[str, ...], titles: dict[str, str]
) -> dict[str, Any]:
    """Create a canonical JSON-serializable snapshot of validated grouped response."""
    # Ensure validation by invoking group_criterion_scores
    scores = group_criterion_scores(parsed, codes, titles)
    return {
        "summary": str(parsed["summary"]),
        "criterion_scores": [
            {
                "criterion_id": s.criterion_id,
                "criterion_title": s.criterion_title,
                "score": s.score,
                "justification": s.justification,
                "evidence": list(s.evidence),
            }
            for s in scores
        ],
    }


__all__ = [
    "build_group_response_schema",
    "canonical_group_response_snapshot",
    "parse_group_response",
    "group_criterion_scores",
    "repair_hint",
]
