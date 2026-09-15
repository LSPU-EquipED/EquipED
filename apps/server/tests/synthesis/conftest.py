"""Shared fakes and fixtures for synthesis module tests."""

from __future__ import annotations


def make_agent_result(
    agent_name: str,
    overall_score: float,
    status: str = "completed",
    criteria_count: int = 0,
):
    """Build a lightweight AgentResult-like object for testing."""

    class FakeAgentResult:
        def __init__(self, agent_name, subtotal, status, criteria_count):
            self.agent_name = agent_name
            self.subtotal = subtotal
            self.success = status == "completed"
            self.error_message = None if self.success else "failed"
            self.criterion_scores = tuple(range(criteria_count))

    return FakeAgentResult(agent_name, overall_score, status, criteria_count)


def make_scored_agent(agent_id: str, subtotal: float, criteria_count: int = 1):
    return make_agent_result(
        agent_id,
        float(subtotal),
        status="completed",
        criteria_count=criteria_count,
    )
