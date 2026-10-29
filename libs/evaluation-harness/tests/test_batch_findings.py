"""Validation tests for the retained saved Coordinator finding contract."""

from __future__ import annotations

import pytest
from equiped_harness.agents.coordinator import batch_findings as module
from equiped_harness.exceptions import AgentExecutionError


def test_batch_validator_preserves_model_text_and_frozen_order():
    ids = ("OP-01", "OP-02")
    scores = {"OP-01": 2, "OP-02": 4}
    rows = [
        {
            "criterion_id": cid,
            "score": scores[cid],
            "finding": f"Exact model text for {cid}.",
        }
        for cid in ids
    ]
    data = module.validate_response({"results": rows}, ids, scores)
    assert data["results"] == rows
    with pytest.raises(AgentExecutionError):
        module.validate_response({"results": list(reversed(rows))}, ids, scores)
