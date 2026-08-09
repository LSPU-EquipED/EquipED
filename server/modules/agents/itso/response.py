"""ITSO response parsing and criterion conversion."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError


def _failure(category: str, value: Any) -> AgentExecutionError:
    reference = hashlib.sha256(str(value).encode()).hexdigest()[:16]
    return AgentExecutionError(f"{category} (reference: {reference})")


def parse_response(raw: str, agent_name: str = "itso") -> dict[str, Any]:
    if not isinstance(raw, str):
        raise _failure("ITSOResponseTypeError", type(raw).__name__)
    payload = raw.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", payload, flags=re.I | re.S)
    if match:
        payload = match.group(1).strip()
    elif not payload.startswith("{"):
        start, end = payload.find("{"), payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start : end + 1].strip()
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise _failure("ITSOInvalidJSON", raw) from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("summary", ""), str):
        raise _failure("ITSOInvalidResponse", type(parsed).__name__)
    if not isinstance(parsed.get("criterion_scores"), (list, dict)):
        raise _failure(
            "ITSOInvalidCriterionScores", type(parsed.get("criterion_scores")).__name__
        )
    return parsed


def criterion_scores(
    parsed: dict[str, Any], agent_name: str = "itso"
) -> tuple[CriterionScore, ...]:
    raw = parsed["criterion_scores"]
    entries = (
        [
            {
                "criterion_id": key,
                **(value if isinstance(value, dict) else {"score": value}),
            }
            for key, value in raw.items()
        ]
        if isinstance(raw, dict)
        else raw
    )
    result = []
    for index, item in enumerate(entries):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("criterion_id"), str)
            or not item["criterion_id"]
        ):
            raise _failure("ITSOInvalidCriterion", index)
        score = item.get("score")
        if isinstance(score, bool):
            score = None
        if isinstance(score, float) and math.isfinite(score) and score.is_integer():
            score = int(score)
        if isinstance(score, str):
            try:
                numeric = float(score.strip())
                score = (
                    int(numeric)
                    if math.isfinite(numeric) and numeric.is_integer()
                    else None
                )
            except (TypeError, ValueError, OverflowError):
                score = None
        if not isinstance(score, int):
            raise _failure("ITSOInvalidScore", index)
        result.append(
            CriterionScore(
                criterion_id=item["criterion_id"],
                criterion_title=(
                    item["criterion_title"]
                    if isinstance(item.get("criterion_title"), str)
                    else item["criterion_id"]
                ),
                score=score,
                justification=str(item.get("justification", "")),
                chunk_ids=_normalize_text_tuple(item.get("chunk_ids", ())),
                evidence=_normalize_text_tuple(item.get("evidence", ())),
            )
        )
    return tuple(result)


def _normalize_text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()
