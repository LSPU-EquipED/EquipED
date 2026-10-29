"""Compatibility helpers for saved Coordinator objective reviews."""

from __future__ import annotations

from typing import Any

from equiped_harness.exceptions import AgentExecutionError

UNIT_REVIEW_BATCH_SIZE = 1


def apply_objective_reviews(
    rows: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Apply ordered semantic decisions to normalized objective rows."""
    for decision in decisions:
        if (
            not isinstance(decision, dict)
            or set(decision) != {"objective_id", "decision", "reason"}
            or not isinstance(decision["decision"], str)
            or decision["decision"] not in {"qualifies", "does_not_qualify"}
            or not isinstance(decision["reason"], str)
            or not decision["reason"].strip()
            or len(decision["reason"]) > 500
        ):
            raise AgentExecutionError("Objective review decision is invalid")
    expected = [row["objective_id"] for row in rows if row.get("matches")]
    actual = [row.get("objective_id") for row in decisions]
    if actual != expected:
        raise AgentExecutionError(
            "Objective decisions do not cover positive rows in order"
        )
    by_id = {decision["objective_id"]: decision for decision in decisions}
    updated_rows = []
    for row in rows:
        updated = dict(row)
        decision = by_id.get(row["objective_id"]) if row.get("matches") else None
        if decision is not None:
            updated["reason"] = decision["reason"].strip()
            if decision["decision"] == "does_not_qualify":
                updated["matches"] = []
                updated["source_ids"] = []
        updated_rows.append(updated)
    return updated_rows
