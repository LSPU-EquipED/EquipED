"""ITSO response parsing and criterion conversion."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError


def _failure(category: str, value: Any) -> AgentExecutionError:
    reference = hashlib.sha256(str(value).encode()).hexdigest()[:16]
    return AgentExecutionError(f"{category} (reference: {reference})")


ITSO_RESPONSE_SCHEMA_VERSION = "itso-response-v1"
ITSO_CRITERIA_TITLES = {
    "ITSO-01": "No IP Issue — absence of plagiarism indicators",
    "ITSO-02": "Proper References — sources properly acknowledged",
    "ITSO-03": "Faculty Ownership — intellectual property rights respected",
    "ITSO-04": "Student Confidentiality — student data protected",
    "ITSO-05": "Teacher and Student Rights — digital rights preserved",
}
ITSO_CRITERIA = tuple(ITSO_CRITERIA_TITLES)
ITSO_TEXT_MAX = 2000
ITSO_CHUNK_ID_MAX = 2000
ITSO_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "criterion_scores"],
    "properties": {
        "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
        "criterion_scores": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "prefixItems": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "criterion_id",
                        "criterion_title",
                        "score",
                        "justification",
                        "chunk_ids",
                        "evidence",
                    ],
                    "properties": {
                        "criterion_id": {"const": criterion_id},
                        "criterion_title": {"const": title},
                        "score": {"type": "integer", "minimum": 1, "maximum": 4},
                        "justification": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ITSO_TEXT_MAX,
                        },
                        "chunk_ids": {
                            "type": "array",
                            "maxItems": 8,
                            "items": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": ITSO_CHUNK_ID_MAX,
                            },
                        },
                        "evidence": {
                            "type": "array",
                            "maxItems": 8,
                            "items": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": ITSO_TEXT_MAX,
                            },
                        },
                    },
                }
                for criterion_id, title in ITSO_CRITERIA_TITLES.items()
            ],
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "criterion_id",
                    "criterion_title",
                    "score",
                    "justification",
                    "chunk_ids",
                    "evidence",
                ],
                "properties": {
                    "criterion_id": {"type": "string", "maxLength": 32},
                    "criterion_title": {"type": "string", "maxLength": 256},
                    "score": {"type": "integer", "minimum": 1, "maximum": 4},
                    "justification": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": ITSO_TEXT_MAX,
                    },
                    "chunk_ids": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ITSO_CHUNK_ID_MAX,
                        },
                    },
                    "evidence": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ITSO_TEXT_MAX,
                        },
                    },
                },
            },
            "unevaluatedItems": False,
        },
    },
}


def build_response_schema(known_chunk_ids: Iterable[str]) -> dict[str, Any]:
    """Build a bounded contract for the immutable chunk-id set of one task."""
    ids = tuple(dict.fromkeys(str(chunk_id) for chunk_id in known_chunk_ids))
    schema = json.loads(json.dumps(ITSO_RESPONSE_SCHEMA))
    chunk_schema = {
        "type": "array",
        "maxItems": 8 if ids else 0,
        "items": {"enum": list(ids)} if ids else False,
    }
    scores = schema["properties"]["criterion_scores"]
    for item in (*scores["prefixItems"], scores["items"]):
        item["properties"]["chunk_ids"] = chunk_schema
    return schema


def parse_response(
    raw: str,
    agent_name: str = "itso",
    *,
    expected_ids: Iterable[str] = ITSO_CRITERIA,
    known_chunk_ids: Iterable[str] = (),
) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise _failure("ITSOResponseTypeError", type(raw).__name__)
    payload = raw.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", payload, flags=re.I | re.S)
    if match:
        payload = match.group(1).strip()
    elif not payload.startswith("{"):
        raise _failure("ITSOInvalidJSON", raw)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise _failure("ITSOInvalidJSON", raw) from exc
    if (
        not isinstance(parsed, dict)
        or set(parsed) != {"summary", "criterion_scores"}
        or not isinstance(parsed.get("summary"), str)
        or not 1 <= len(parsed["summary"]) <= 2000
    ):
        raise _failure("ITSOInvalidResponse", type(parsed).__name__)
    if not isinstance(parsed.get("criterion_scores"), (list, dict)):
        raise _failure(
            "ITSOInvalidCriterionScores", type(parsed.get("criterion_scores")).__name__
        )
    criterion_scores(parsed, expected_ids=expected_ids, known_chunk_ids=known_chunk_ids)
    return parsed


def criterion_scores(
    parsed: dict[str, Any],
    agent_name: str = "itso",
    *,
    expected_ids: Iterable[str] = ITSO_CRITERIA,
    known_chunk_ids: Iterable[str] = (),
) -> tuple[CriterionScore, ...]:
    raw = parsed["criterion_scores"]
    entries = raw
    expected = tuple(expected_ids)
    known = set(known_chunk_ids)
    if not isinstance(entries, list) or len(entries) != len(expected):
        raise _failure("ITSOInvalidCriterionScores", "shape")
    seen = set()
    result = []
    for index, item in enumerate(entries):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("criterion_id"), str)
            or item["criterion_id"] not in expected
            or item["criterion_id"] in seen
            or set(item)
            != {
                "criterion_id",
                "criterion_title",
                "score",
                "justification",
                "chunk_ids",
                "evidence",
            }
        ):
            raise _failure("ITSOInvalidCriterion", index)
        if index >= len(expected) or item["criterion_id"] != expected[index]:
            raise _failure("ITSOInvalidCriterionOrder", index)
        title = item["criterion_title"]
        if title != ITSO_CRITERIA_TITLES[item["criterion_id"]]:
            raise _failure("ITSOInvalidCriterionTitle", index)
        seen.add(item["criterion_id"])
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 4:
            raise _failure("ITSOInvalidScore", index)
        justification = item["justification"]
        if (
            not isinstance(justification, str)
            or not justification
            or len(justification) > ITSO_TEXT_MAX
        ):
            raise _failure("ITSOInvalidJustification", index)
        result.append(
            CriterionScore(
                criterion_id=item["criterion_id"],
                criterion_title=item["criterion_title"],
                score=score,
                justification=item["justification"],
                chunk_ids=_normalize_text_tuple(
                    item["chunk_ids"], ITSO_CHUNK_ID_MAX, known
                ),
                evidence=_normalize_text_tuple(item["evidence"], ITSO_TEXT_MAX),
            )
        )
    if seen != set(expected):
        raise _failure("ITSOInvalidCriterion", "set")
    return tuple(result)


def _normalize_text_tuple(
    value: Any, max_length: int, known: set[str] | None = None
) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or len(value) > 8
        or any(
            not isinstance(item, str) or not item or len(item) > max_length
            for item in value
        )
    ):
        raise _failure("ITSOInvalidEvidence", "shape")
    result = tuple(value)
    if known is not None and any(item not in known for item in result):
        raise _failure("ITSOUnknownChunk", "id")
    return result
