"""Historical Coordinator narrative response validation."""

from __future__ import annotations

from typing import Any

from equiped_harness.agents.coordinator.model_findings import (
    validate_finding_response,
    validate_summary_response,
)
from equiped_harness.exceptions import AgentExecutionError

BATCH_CONTRACT = "coordinator_findings_batch.v1"
ORGANIZATION_KEY = "findings-organization"
ASSESSMENT_KEY = "findings-assessment"
ORGANIZATION_IDS = ("OP-01", "OP-02", "OP-03", "OP-04", "OP-05")
ASSESSMENT_IDS = ("A-01", "A-02", "A-03", "A-04", "A-05", "C-01")
FINAL_KEYS = (ORGANIZATION_KEY, ASSESSMENT_KEY)


def validate_response(
    data: Any,
    codes: tuple[str, ...],
    score_by_code: dict[str, int],
    *,
    summary: bool = False,
    fallback: bool = False,
) -> dict[str, Any]:
    """Validate batch identity, order, scores and individual findings."""
    required = {"results", "summary"} if summary else {"results"}
    if not isinstance(data, dict) or set(data) != required:
        raise AgentExecutionError("finding batch fields are invalid")
    rows = data["results"]
    if not isinstance(rows, list) or len(rows) != len(codes):
        raise AgentExecutionError("finding batch result count is invalid")
    normalized = []
    for row, code in zip(rows, codes, strict=True):
        checked = validate_finding_response(
            {"results": [row]}, code, score_by_code[code], fallback=fallback
        )
        normalized.append(checked["results"][0])
    result = {"results": normalized}
    if summary:
        result["summary"] = validate_summary_response(
            {"results": [{"summary": data["summary"]}]}, fallback=fallback
        )
    return result
