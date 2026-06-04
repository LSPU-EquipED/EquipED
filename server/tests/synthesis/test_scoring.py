"""Unit tests for synthesis scoring logic."""

from __future__ import annotations

import pytest

from server.modules.synthesis.matrix import AGENT_WEIGHTS, compute_synthesized_score
from server.tests.synthesis.conftest import make_agent_result, make_scored_agent


def test_weighted_score_all_passing() -> None:
    agent_results = [
        make_scored_agent("sme", 4.0),
        make_scored_agent("coordinator", 4.0),
        make_scored_agent("gad", 4.0),
        make_scored_agent("itso", 4.0),
    ]

    result = compute_synthesized_score(agent_results)

    assert result["synthesized_score"] == pytest.approx(100.0)
    assert result["is_partial"] is False
    assert result["active_agents"] == ["sme", "coordinator", "gad", "itso"]
    assert result["failed_agents"] == []
    assert set(result["domain_scores"]) == {"sme", "coordinator", "gad", "itso"}
    for agent_id, domain in result["domain_scores"].items():
        assert domain["subtotal"] == 4.0
        assert domain["status"] == "OK"
        assert domain["max_score"] == 4
        assert AGENT_WEIGHTS[agent_id] > 0


def test_weighted_score_mixed_scores() -> None:
    agent_results = [
        make_scored_agent("sme", 3.2),
        make_scored_agent("coordinator", 2.8),
        make_scored_agent("gad", 3.6),
        make_scored_agent("itso", 2.4),
    ]

    result = compute_synthesized_score(agent_results)

    assert result["synthesized_score"] == pytest.approx(76.0)
    assert result["is_partial"] is False


def test_weighted_score_one_failed() -> None:
    sme = make_scored_agent("sme", 3.2)
    coord = make_scored_agent("coordinator", 2.8)
    gad = make_scored_agent("gad", 2.0)
    itso = make_agent_result("itso", 0.0, status="failed")

    result = compute_synthesized_score([sme, coord, gad, itso])

    assert result["is_partial"] is True
    assert result["failed_agents"] == ["itso"]
    assert result["domain_scores"]["itso"]["status"] == "ERROR"
    assert result["domain_scores"]["itso"]["subtotal"] == 0.0
    assert result["synthesized_score"] == pytest.approx(69.41, abs=0.01)


def test_weighted_score_all_failed() -> None:
    result = compute_synthesized_score(
        [
            make_agent_result("sme", 0.0, status="failed"),
            make_agent_result("coordinator", 0.0, status="failed"),
            make_agent_result("gad", 0.0, status="failed"),
            make_agent_result("itso", 0.0, status="failed"),
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

    single = compute_synthesized_score([make_scored_agent("sme", 3.6)])
    assert single["synthesized_score"] == pytest.approx(90.0)
    assert single["is_partial"] is False


def test_weighted_score_weights_sum_to_one() -> None:
    assert sum(AGENT_WEIGHTS.values()) == pytest.approx(1.0)


def test_normalization_weight_format() -> None:
    result = compute_synthesized_score([make_scored_agent("sme", 4.0)])

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
