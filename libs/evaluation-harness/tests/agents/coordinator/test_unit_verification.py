"""Compatibility behavior for saved Coordinator objective reviews."""

import pytest
from equiped_harness.agents.coordinator.unit_verification import apply_objective_reviews
from equiped_harness.exceptions import AgentExecutionError


def _objective_row(objective_id, *quotes):
    return {
        "objective_id": objective_id,
        "matches": [{"source_id": "slm-1", "quote": quote} for quote in quotes],
        "source_ids": ["slm-1"] if quotes else [],
        "reason": "untrusted primary reason",
    }


def test_apply_objective_reviews_requires_exact_positive_row_order():
    rows = [_objective_row("o1", "quote"), _objective_row("o2", "other")]
    decisions = [{"objective_id": "o2", "decision": "qualifies", "reason": "ok."}]
    with pytest.raises(AgentExecutionError):
        apply_objective_reviews(rows, decisions)


def test_apply_objective_reviews_preserves_unsupported_rows_and_cleans_reasons():
    rows = [
        _objective_row("o1"),
        _objective_row("o2", "Supported excerpt."),
        _objective_row("o3", "Another excerpt."),
    ]
    decisions = [
        {
            "objective_id": "o2",
            "decision": "does_not_qualify",
            "reason": " Unsupported. ",
        },
        {"objective_id": "o3", "decision": "qualifies", "reason": " Supported. "},
    ]
    applied = apply_objective_reviews(rows, decisions)
    assert [row["objective_id"] for row in applied] == ["o1", "o2", "o3"]
    assert applied[0] == rows[0]
    assert applied[1]["matches"] == applied[1]["source_ids"] == []
    assert applied[1]["reason"] == "Unsupported."
    assert applied[2]["matches"] == rows[2]["matches"]
    assert applied[2]["reason"] == "Supported."


@pytest.mark.parametrize(
    "decision",
    [
        {"objective_id": "unknown", "decision": "qualifies", "reason": "ok"},
        {"objective_id": "o2", "decision": "qualifies", "reason": "ok"},
    ],
)
def test_apply_objective_reviews_rejects_wrong_ids_or_order(decision):
    with pytest.raises(AgentExecutionError):
        apply_objective_reviews([_objective_row("o1", "quote")], [decision])


@pytest.mark.parametrize("decision", ["maybe", "not_a_unit", ""])
def test_apply_objective_reviews_rejects_invalid_decision_labels(decision):
    with pytest.raises(AgentExecutionError):
        apply_objective_reviews(
            [_objective_row("o1", "quote")],
            [{"objective_id": "o1", "decision": decision, "reason": "why"}],
        )


@pytest.mark.parametrize("reason", ["", "  ", "x" * 501])
def test_apply_objective_reviews_rejects_invalid_reasons(reason):
    with pytest.raises(AgentExecutionError):
        apply_objective_reviews(
            [_objective_row("o1", "quote")],
            [{"objective_id": "o1", "decision": "qualifies", "reason": reason}],
        )
