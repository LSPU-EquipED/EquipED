"""Tests for coordinator resource-affinity domain packing."""

from __future__ import annotations

import uuid

import pytest
from server.modules.agents.coordinator.packing import pack_domains
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    DomainDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)


def _make_criterion(code: str, title: str, order: int = 0) -> CriterionDefinition:
    """Create a criterion definition."""
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=title,
        description=f"Description for {title}",
        display_order=order,
        strategy_config=LlmRubricGuidanceConfig(guidance="Evaluate criterion."),
    )


def _make_realistic_criterion(code: str, order: int = 0) -> CriterionDefinition:
    if code == "A-05":
        config = CurriculumAlignmentConfig()  # type: ignore[assignment]
    elif code in ("OP-02", "OP-05", "A-02", "A-03", "A-04"):
        config = CountBandConfig(  # type: ignore[assignment]
            mode="minimum_count", threshold_4=4, threshold_3=2, threshold_2=1
        )
    else:
        config = RatioBandConfig(  # type: ignore[assignment]
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        )
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=f"{code} title",
        description=f"Description for {code}",
        display_order=order,
        strategy_config=config,
    )


def test_op_and_a_domains_pack_into_three_resource_envelopes():
    """OP (OP-01..OP-05) + A (A-01..A-05) -> 3 resource-affinity envelopes."""
    op_criteria = tuple(
        _make_criterion(f"OP-{i:02d}", f"OP Criterion {i}", i - 1) for i in range(1, 6)
    )
    a_criteria = tuple(
        _make_criterion(f"A-{i:02d}", f"A Criterion {i}", i - 1) for i in range(1, 6)
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
    assert len(envelopes) == 3
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
    ]
    assert [c.criterion_code for c in envelopes[2]] == ["A-05"]


def test_realistic_configs_pack_a01_and_a05_separately():
    """A-01 ratio band and A-05 curriculum alignment run in separate envelopes."""
    op_criteria = tuple(
        _make_realistic_criterion(f"OP-{i:02d}", i - 1) for i in range(1, 6)
    )
    a_criteria = tuple(
        _make_realistic_criterion(f"A-{i:02d}", i - 1) for i in range(1, 6)
    )
    domains = (
        DomainDefinition(
            rubric_domain_id=uuid.uuid4(),
            code="OP",
            title="Organization & Presentation",
            display_order=0,
            criteria=op_criteria,
        ),
        DomainDefinition(
            rubric_domain_id=uuid.uuid4(),
            code="A",
            title="Assessment",
            display_order=1,
            criteria=a_criteria,
        ),
    )
    envelopes = pack_domains(domains)
    assert len(envelopes) == 3
    assert [c.criterion_code for c in envelopes[1]] == [
        "A-01",
        "A-02",
        "A-03",
        "A-04",
    ]
    assert [c.criterion_code for c in envelopes[2]] == ["A-05"]
    assert len(envelopes) <= 3


def test_historical_adapter_v1_single_a05_produces_one_envelope():
    """Single A-05 criterion (adapter-v1) -> 1 envelope ((A-05,),)."""
    crit = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="A-05",
        title="Curriculum Alignment",
        description="Evaluate alignment.",
        display_order=0,
        strategy_config=CurriculumAlignmentConfig(),
    )
    domains = (
        DomainDefinition(
            rubric_domain_id=uuid.uuid4(),
            code="A",
            title="Assessment",
            display_order=0,
            criteria=(crit,),
        ),
    )
    envelopes = pack_domains(domains)
    assert len(envelopes) == 1
    assert envelopes == ((crit,),)
    assert [c.criterion_code for c in envelopes[0]] == ["A-05"]


def test_single_domain_preserves_contiguous_ordering():
    """Single domain without curriculum collision stays in one envelope."""
    criteria = tuple(
        _make_criterion(f"OP-{i:02d}", f"OP {i}", i - 1) for i in range(1, 4)
    )
    domains = (
        DomainDefinition(
            rubric_domain_id=uuid.uuid4(),
            code="OP",
            title="Operational",
            display_order=0,
            criteria=criteria,
        ),
    )
    envelopes = pack_domains(domains)
    assert len(envelopes) == 1
    assert [c.criterion_code for c in envelopes[0]] == ["OP-01", "OP-02", "OP-03"]


def test_no_criteria_raises():
    """Empty domains tuple raises AgentExecutionError."""
    with pytest.raises(AgentExecutionError):
        pack_domains(())
