"""Unit tests for synthesis scoring logic."""

from __future__ import annotations

import pytest

from server.modules.synthesis.matrix import AGENT_WEIGHTS, compute_synthesized_score
from server.modules.synthesis.schemas import score_to_adjectival
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
    assert result["overall_score"] == pytest.approx(4.0)
    assert result["adjectival_rating"] == "Very Satisfactory"
    assert result["is_partial"] is False
    assert result["active_agents"] == ["sme", "coordinator", "gad", "itso"]
    assert result["failed_agents"] == []
    assert set(result["domain_scores"]) == {"sme", "coordinator", "gad", "itso"}
    for agent_id, domain in result["domain_scores"].items():
        assert domain["subtotal"] == 4.0
        assert domain["status"] == "OK"
        assert domain["max_score"] == 4
        assert domain["adjectival_rating"] == "Very Satisfactory"
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
    assert result["overall_score"] == pytest.approx(3.04)
    assert result["adjectival_rating"] == "Satisfactory"
    assert result["domain_scores"]["sme"]["adjectival_rating"] == "Satisfactory"
    assert result["domain_scores"]["coordinator"]["adjectival_rating"] == "Satisfactory"
    assert result["domain_scores"]["gad"]["adjectival_rating"] == "Very Satisfactory"
    assert result["domain_scores"]["itso"]["adjectival_rating"] == "Needs Improvement"
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
    assert result["domain_scores"]["itso"]["adjectival_rating"] is None
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
    assert result["overall_score"] is None
    assert result["adjectival_rating"] is None
    assert result["is_partial"] is True
    assert result["active_agents"] == []


def test_weighted_score_edge_cases() -> None:
    empty = compute_synthesized_score([])
    assert empty["synthesized_score"] == 0.0
    assert empty["overall_score"] is None
    assert empty["adjectival_rating"] is None
    assert empty["is_partial"] is False
    assert empty["domain_scores"] == {}

    single = compute_synthesized_score([make_scored_agent("sme", 3.6)])
    assert single["synthesized_score"] == pytest.approx(90.0)
    assert single["overall_score"] == pytest.approx(3.6)
    assert single["adjectival_rating"] == "Very Satisfactory"
    assert single["is_partial"] is False


def test_weighted_score_weights_sum_to_one() -> None:
    assert sum(AGENT_WEIGHTS.values()) == pytest.approx(1.0)


def test_normalization_weight_format() -> None:
    result = compute_synthesized_score([make_scored_agent("sme", 4.0)])

    assert set(result) == {
        "synthesized_score",
        "overall_score",
        "adjectival_rating",
        "domain_scores",
        "active_agents",
        "failed_agents",
        "is_partial",
        "partial_reason",
    }
    assert set(result["domain_scores"]["sme"]) == {
        "criteria",
        "subtotal",
        "max_score",
        "status",
        "adjectival_rating",
    }


def test_force_partial_without_failed_agents_sets_is_partial() -> None:
    """force_partial=True marks result as partial even without any failed agents."""
    agent_results = [
        make_scored_agent("sme", 3.2),
        make_scored_agent("gad", 3.6),
        make_scored_agent("itso", 2.4),
    ]
    result = compute_synthesized_score(
        agent_results,
        force_partial=True,
        partial_reason="No curriculum reference was available; Coordinator review was skipped.",
    )

    assert result["is_partial"] is True
    assert result["partial_reason"] is not None
    assert "curriculum" in result["partial_reason"].lower()
    assert result["failed_agents"] == []
    assert "coordinator" not in result["active_agents"]
    assert result["synthesized_score"] > 0
    # Weights: sme=0.35, gad=0.20, itso=0.15, sum=0.70
    # Normalized: sme=0.5, gad=0.2857, itso=0.2143
    # Pct: sme=80, gad=90, itso=60
    # Synthesized: 0.5*80 + 0.2857*90 + 0.2143*60 ≈ 78.57
    assert result["synthesized_score"] == pytest.approx(78.57, abs=0.01)


def test_force_partial_no_partial_reason_when_not_forced() -> None:
    """partial_reason is None in the result when is_partial is False."""
    agent_results = [
        make_scored_agent("sme", 4.0),
        make_scored_agent("coordinator", 4.0),
        make_scored_agent("gad", 4.0),
        make_scored_agent("itso", 4.0),
    ]
    result = compute_synthesized_score(agent_results)

    assert result["is_partial"] is False
    assert result.get("partial_reason") is None


def test_force_partial_with_actual_failed_agents() -> None:
    """When force_partial and actual failures both apply, partial_reason from
    force_partial is returned and is_partial is True."""
    agent_results = [
        make_scored_agent("sme", 3.0),
        make_agent_result("gad", 0.0, status="failed"),
        make_scored_agent("itso", 3.0),
    ]
    result = compute_synthesized_score(
        agent_results,
        force_partial=True,
        partial_reason="Test partial reason",
    )

    assert result["is_partial"] is True
    assert result["failed_agents"] == ["gad"]
    assert result["partial_reason"] == "Test partial reason"


def test_normalization_with_three_agents_no_coordinator() -> None:
    """Without coordinator agent in results, weights normalize to sum=100%."""
    agent_results = [
        make_scored_agent("sme", 4.0),
        make_scored_agent("gad", 4.0),
        make_scored_agent("itso", 4.0),
    ]
    result = compute_synthesized_score(agent_results)

    # All succeed, no force_partial — should NOT be marked partial
    assert result["is_partial"] is False
    assert result["synthesized_score"] == pytest.approx(100.0)
    assert result["active_agents"] == ["sme", "gad", "itso"]
    assert result["failed_agents"] == []

    # With force_partial=True it should be marked partial
    result2 = compute_synthesized_score(
        agent_results,
        force_partial=True,
        partial_reason="Coordinator was skipped",
    )
    assert result2["is_partial"] is True
    assert result2["partial_reason"] == "Coordinator was skipped"
    # Score should be same (normalization with 3 agents)
    assert result2["synthesized_score"] == pytest.approx(100.0)


# --- Adjectival rating unit tests ---


def test_score_to_adjectival_very_satisfactory() -> None:
    assert score_to_adjectival(4.0) == "Very Satisfactory"
    assert score_to_adjectival(3.75) == "Very Satisfactory"
    assert score_to_adjectival(3.50) == "Very Satisfactory"


def test_score_to_adjectival_satisfactory() -> None:
    assert score_to_adjectival(3.49) == "Satisfactory"
    assert score_to_adjectival(3.0) == "Satisfactory"
    assert score_to_adjectival(2.50) == "Satisfactory"


def test_score_to_adjectival_needs_improvement() -> None:
    assert score_to_adjectival(2.49) == "Needs Improvement"
    assert score_to_adjectival(2.0) == "Needs Improvement"
    assert score_to_adjectival(1.50) == "Needs Improvement"


def test_score_to_adjectival_poor() -> None:
    assert score_to_adjectival(1.49) == "Poor"
    assert score_to_adjectival(1.0) == "Poor"
    assert score_to_adjectival(0.0) == "Poor"


def test_score_to_adjectival_boundaries() -> None:
    """Test boundary conditions between each rating tier."""
    # Just above threshold
    assert score_to_adjectival(3.51) == "Very Satisfactory"
    # Just below threshold
    assert score_to_adjectival(3.49) == "Satisfactory"
    assert score_to_adjectival(2.49) == "Needs Improvement"
    assert score_to_adjectival(1.49) == "Poor"
