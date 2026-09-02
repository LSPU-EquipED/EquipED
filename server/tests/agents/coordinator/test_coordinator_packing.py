"""Tests for coordinator domain packing."""

from __future__ import annotations

import uuid

import pytest
from server.modules.agents.coordinator.packing import pack_domains
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.rubrics.contracts import (
    CriterionDefinition,
    DomainDefinition,
    LlmRubricGuidanceConfig,
)


def _make_criterion(
    code: str, title: str, order: int = 0
) -> CriterionDefinition:
    """Create a criterion definition."""
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=title,
        description=f"Description for {title}",
        display_order=order,
        strategy_config=LlmRubricGuidanceConfig(guidance="Evaluate criterion."),
    )


def test_op_and_a_domains_pack_into_two_ordered_envelopes():
    """OP domain (OP-01..OP-05) + A domain (A-01..A-05) -> 2 envelopes."""
    op_criteria = tuple(
        _make_criterion(f"OP-{i:02d}", f"OP Criterion {i}", i - 1)
        for i in range(1, 6)
    )
    a_criteria = tuple(
        _make_criterion(f"A-{i:02d}", f"A Criterion {i}", i - 1)
        for i in range(1, 6)
    )

    domains = (
        DomainDefinition(
            rubric_domain_id=uuid.uuid4(),
            code="OP",
            title="Operational Domain",
            display_order=0,
            criteria=op_criteria,
        ),
        DomainDefinition(
            rubric_domain_id=uuid.uuid4(),
            code="A",
            title="Assessment Domain",
            display_order=1,
            criteria=a_criteria,
        ),
    )

    envelopes = pack_domains(domains)
    assert len(envelopes) == 2
    assert [c.criterion_code for c in envelopes[0]] == [
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
    ]
    assert [c.criterion_code for c in envelopes[1]] == [
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
    ]


def test_no_criteria_raises():
    """Empty domains tuple raises AgentExecutionError."""
    with pytest.raises(AgentExecutionError):
        pack_domains(())
