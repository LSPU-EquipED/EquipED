"""Unit tests for synthesis scoring and monitoring matrix payloads."""

from __future__ import annotations

import uuid

import pytest

from server.modules.synthesis.matrix import AGENT_WEIGHTS, compute_synthesized_score


def _make_agent_result(
    agent_name: str,
    overall_score: float,
    status: str = "completed",
):
    """Build a lightweight AgentResult-like object for testing."""

    class FakeAgentResult:
        def __init__(self, agent_name, subtotal, status):
            self.agent_name = agent_name
            self.subtotal = subtotal
            self.success = status == "completed"
            self.error_message = None if self.success else "failed"

    return FakeAgentResult(agent_name, overall_score, status)


def _make_scored_agent(agent_id: str, subtotal: float, criteria_count: int = 1):
    result = _make_agent_result(agent_id, float(subtotal), status="completed")
    return result


def test_weighted_score_all_passing() -> None:
    agent_results = [
        _make_scored_agent("sme", 4.0),
        _make_scored_agent("coordinator", 4.0),
        _make_scored_agent("gad", 4.0),
        _make_scored_agent("itso", 4.0),
    ]

    result = compute_synthesized_score(agent_results)

    assert result["synthesized_score"] == pytest.approx(100.0)
    assert result["is_partial"] is False
    assert result["active_agents"] == ["sme", "coordinator", "gad", "itso"]
    assert result["failed_agents"] == []
    assert set(result["domain_scores"]) == {"sme", "coordinator", "gad", "itso"}
    for agent_id, domain in result["domain_scores"].items():
        assert domain["subtotal"] == 4.0
        assert domain["status"] == "completed"
        assert domain["max_score"] == 4
        assert AGENT_WEIGHTS[agent_id] > 0


def test_weighted_score_mixed_scores() -> None:
    agent_results = [
        _make_scored_agent("sme", 3.2),
        _make_scored_agent("coordinator", 2.8),
        _make_scored_agent("gad", 3.6),
        _make_scored_agent("itso", 2.4),
    ]

    result = compute_synthesized_score(agent_results)

    assert result["synthesized_score"] == pytest.approx(76.0)
    assert result["is_partial"] is False


def test_weighted_score_one_failed() -> None:
    sme = _make_scored_agent("sme", 3.2)
    coord = _make_scored_agent("coordinator", 2.8)
    gad = _make_scored_agent("gad", 2.0)
    itso = _make_agent_result("itso", 0.0, status="failed")

    result = compute_synthesized_score([sme, coord, gad, itso])

    assert result["is_partial"] is True
    assert result["failed_agents"] == ["itso"]
    assert result["domain_scores"]["itso"]["status"] == "failed"
    assert result["domain_scores"]["itso"]["subtotal"] == 0.0
    assert result["synthesized_score"] == pytest.approx(69.41, abs=0.01)


def test_weighted_score_all_failed() -> None:
    result = compute_synthesized_score(
        [
            _make_agent_result("sme", 0.0, status="failed"),
            _make_agent_result("coordinator", 0.0, status="failed"),
            _make_agent_result("gad", 0.0, status="failed"),
            _make_agent_result("itso", 0.0, status="failed"),
        ]
    )

    assert result["synthesized_score"] == 0.0
    assert result["is_partial"] is True
    assert result["active_agents"] == []


def test_weighted_score_edge_cases() -> None:
    empty = compute_synthesized_score([])
    assert empty["synthesized_score"] == 0.0
    assert empty["is_partial"] is False
    assert empty["domain_scores"] == {}

    single = compute_synthesized_score([_make_scored_agent("sme", 3.6)])
    assert single["synthesized_score"] == pytest.approx(90.0)
    assert single["is_partial"] is False


def test_weighted_score_weights_sum_to_one() -> None:
    assert sum(AGENT_WEIGHTS.values()) == pytest.approx(1.0)


def test_normalization_weight_format() -> None:
    result = compute_synthesized_score([_make_scored_agent("sme", 4.0)])

    assert set(result) == {
        "synthesized_score",
        "domain_scores",
        "active_agents",
        "failed_agents",
        "is_partial",
    }
    assert set(result["domain_scores"]["sme"]) == {
        "criteria",
        "subtotal",
        "max_score",
        "status",
    }
