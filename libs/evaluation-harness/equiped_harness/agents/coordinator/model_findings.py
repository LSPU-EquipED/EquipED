"""Shared finding contracts and validators for Coordinator results."""

from __future__ import annotations

import re
from typing import Any

from equiped_harness.exceptions import AgentExecutionError

FINDING_CONTRACT = "coordinator_finding.v1"
SUMMARY_CONTRACT = "coordinator_summary.v1"
SUMMARY_UNIT_KEY = "finding-summary"
UNAVAILABLE_FINDING = "Reasoning unavailable—review required."
UNAVAILABLE_SUMMARY = "Specialist summary unavailable—review required."


def finding_unit_key(code: str) -> str:
    return f"finding-{code}"


def validate_finding_response(
    data: Any, code: str, score: int, *, fallback: bool = False
) -> dict[str, Any]:
    if (
        not isinstance(data, dict)
        or set(data) != {"results"}
        or not isinstance(data["results"], list)
        or len(data["results"]) != 1
    ):
        raise AgentExecutionError("finding response requires one result")
    row = data["results"][0]
    if not isinstance(row, dict) or set(row) != {"criterion_id", "score", "finding"}:
        raise AgentExecutionError("finding result fields are invalid")
    if (
        row["criterion_id"] != code
        or type(row["score"]) is not int
        or row["score"] != score
    ):
        raise AgentExecutionError(
            "finding must retain the provided criterion_id and score"
        )
    finding = row["finding"]
    if (
        not isinstance(finding, str)
        or finding != finding.strip()
        or not finding
        or len(finding) > 1600
        or re.fullmatch(r"<[^>]+>", finding)
    ):
        raise AgentExecutionError(
            "finding must be trimmed, nonempty, and at most 1600 characters"
        )
    stated_scores = re.findall(r"\b(\d+(?:\.\d+)?)\s*/\s*4\b", finding)
    stated_scores += re.findall(
        r"\b(?:score|rating)(?:\s+(?:of|is|was))?\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
        finding,
        flags=re.IGNORECASE,
    )
    if any(float(stated) != score for stated in stated_scores):
        raise AgentExecutionError("finding must explain the provided score")
    if fallback and finding != UNAVAILABLE_FINDING:
        raise AgentExecutionError("finding fallback marker is invalid")
    if not fallback and finding == UNAVAILABLE_FINDING:
        raise AgentExecutionError("finding fallback marker requires fallback status")
    return {"results": [{"criterion_id": code, "score": score, "finding": finding}]}


def validate_summary_response(data: Any, *, fallback: bool = False) -> str:
    if (
        not isinstance(data, dict)
        or set(data) != {"results"}
        or not isinstance(data["results"], list)
        or len(data["results"]) != 1
    ):
        raise AgentExecutionError("summary response requires one result")
    row = data["results"][0]
    if not isinstance(row, dict) or set(row) != {"summary"}:
        raise AgentExecutionError("summary result fields are invalid")
    value = row["summary"]
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value
        or len(value) > 1200
    ):
        raise AgentExecutionError(
            "summary must be trimmed, nonempty, and at most 1200 characters"
        )
    if fallback and value != UNAVAILABLE_SUMMARY:
        raise AgentExecutionError("summary fallback marker is invalid")
    if not fallback and value == UNAVAILABLE_SUMMARY:
        raise AgentExecutionError("summary fallback marker requires fallback status")
    return value
