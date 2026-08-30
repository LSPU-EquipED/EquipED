"""Unit tests for pure rubric contracts, strategy schemas, and measurement DTOs."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from server.modules.rubrics.contracts import (
    MAX_CONFIG_JSON_BYTES,
    MAX_DESCRIPTOR_LENGTH,
    MAX_FORM_JSON_BYTES,
    MAX_GUIDANCE_LENGTH,
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    DomainDefinition,
    FormDefinition,
    GroundedInstance,
    GroundedScoreMeasurement,
    GroundedUnit,
    LlmRubricGuidanceConfig,
    LlmScoreDescriptor,
    QualifyingUnitsMeasurement,
    RatioBandConfig,
    ShortSampleConfig,
    calculate_config_json_bytes,
    calculate_form_json_bytes,
    canonicalize_form,
)


def _sample_criterion(
    *,
    criterion_id: uuid.UUID | None = None,
    code: str = "CRIT-01",
    title: str = "Sample Criterion",
    description: str = "Sample description for testing.",
    scoring_rule: str | None = "Standard scoring rule.",
    display_order: int = 0,
    strategy_config: (
        LlmRubricGuidanceConfig
        | CountBandConfig
        | RatioBandConfig
        | CurriculumAlignmentConfig
        | None
    ) = None,
) -> CriterionDefinition:
    return CriterionDefinition(
        rubric_criterion_id=criterion_id or uuid.uuid4(),
        criterion_code=code,
        title=title,
        description=description,
        scoring_rule=scoring_rule,
        display_order=display_order,
        strategy_config=strategy_config
        or LlmRubricGuidanceConfig(guidance="Evaluate content quality."),
    )


def _sample_domain(
    *,
    domain_id: uuid.UUID | None = None,
    code: str = "DOM-01",
    title: str = "Sample Domain",
    display_order: int = 0,
    criteria: tuple[CriterionDefinition, ...] | list[CriterionDefinition] | None = None,
) -> DomainDefinition:
    return DomainDefinition(
        rubric_domain_id=domain_id or uuid.uuid4(),
        code=code,
        title=title,
        display_order=display_order,
        criteria=criteria or (_sample_criterion(),),
    )


def _sample_form(
    *,
    set_id: uuid.UUID | None = None,
    agent_id: str = "sme",
    name: str = "SME Evaluation Form",
    version_number: int = 1,
    adapter_key: str = "sme",
    adapter_version: int = 1,
    domains: tuple[DomainDefinition, ...] | list[DomainDefinition] | None = None,
) -> FormDefinition:
    return FormDefinition(
        rubric_set_id=set_id or uuid.uuid4(),
        agent_id=agent_id,
        name=name,
        version_number=version_number,
        adapter_key=adapter_key,
        adapter_version=adapter_version,
        domains=domains or (_sample_domain(),),
    )


# ---------------------------------------------------------------------------
# Strict Unknown Field & Immutability Tests
# ---------------------------------------------------------------------------


def test_models_forbid_extra_fields() -> None:
    match_msg = "extra_forbidden|Extra inputs are not permitted"
    with pytest.raises(ValidationError, match=match_msg):
        LlmRubricGuidanceConfig(
            guidance="Valid guidance",
            unknown_field="injected",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError, match=match_msg):
        CountBandConfig(
            mode="minimum_count",
            threshold_4=4,
            threshold_3=3,
            threshold_2=2,
            model_override="gpt-4",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError, match=match_msg):
        GroundedScoreMeasurement(
            score=4,
            evidence="Valid evidence text",
            prompt_injection="ignore all rules",  # type: ignore[call-arg]
        )


def test_models_are_recursively_immutable() -> None:
    cfg = LlmRubricGuidanceConfig(guidance="Evaluate structure.")
    with pytest.raises(ValidationError):
        cfg.guidance = "Mutated"  # type: ignore[misc]

    criterion = _sample_criterion(strategy_config=cfg)
    domain = _sample_domain(criteria=[criterion])
    form = _sample_form(domains=[domain])

    # Ensure list arguments were converted to frozen tuples
    assert isinstance(domain.criteria, tuple)
    assert isinstance(form.domains, tuple)

    with pytest.raises(ValidationError):
        form.name = "New Name"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# String Validation & Blank Rejection Tests
# ---------------------------------------------------------------------------


def test_blank_optional_and_required_strings_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty or blank"):
        LlmRubricGuidanceConfig(guidance="   ")

    with pytest.raises(ValueError, match="must not be blank when provided"):
        _sample_criterion(scoring_rule="   ")

    with pytest.raises(ValueError, match="must not be blank when provided"):
        GroundedInstance(excerpt="Valid excerpt", location="   ")

    with pytest.raises(ValueError, match="must not be empty or blank"):
        GroundedUnit(unit_id="   ", evidence="Valid evidence")


# ---------------------------------------------------------------------------
# Strategy Configuration & Bounds Tests
# ---------------------------------------------------------------------------


def test_llm_rubric_guidance_with_optional_level_descriptors() -> None:
    cfg_no_desc = LlmRubricGuidanceConfig(guidance="Evaluate logical coherence.")
    assert cfg_no_desc.strategy == "llm_rubric_guidance"
    assert cfg_no_desc.level_descriptors is None

    descriptors = (
        LlmScoreDescriptor(score=4, descriptor="Exemplary coherence."),
        LlmScoreDescriptor(score=3, descriptor="Adequate coherence."),
        LlmScoreDescriptor(score=2, descriptor="Minor inconsistencies."),
        LlmScoreDescriptor(score=1, descriptor="Major deficiencies."),
    )
    cfg_with_desc = LlmRubricGuidanceConfig(
        guidance="Evaluate logical coherence.",
        level_descriptors=descriptors,
    )
    assert cfg_with_desc.level_descriptors is not None
    assert len(cfg_with_desc.level_descriptors) == 4
    assert {d.score for d in cfg_with_desc.level_descriptors} == {1, 2, 3, 4}


def test_llm_rubric_guidance_invalid_descriptors() -> None:
    with pytest.raises(ValueError, match="exactly 4 entries"):
        LlmRubricGuidanceConfig(
            guidance="Evaluate.",
            level_descriptors=(
                LlmScoreDescriptor(score=4, descriptor="Four"),
                LlmScoreDescriptor(score=3, descriptor="Three"),
                LlmScoreDescriptor(score=2, descriptor="Two"),
            ),
        )

    with pytest.raises(ValueError, match="cover exact scores 1..4"):
        LlmRubricGuidanceConfig(
            guidance="Evaluate.",
            level_descriptors=(
                LlmScoreDescriptor(score=4, descriptor="Four"),
                LlmScoreDescriptor(score=3, descriptor="Three"),
                LlmScoreDescriptor(score=2, descriptor="Two"),
                LlmScoreDescriptor(score=2, descriptor="Two again"),
            ),
        )


def test_count_band_minimum_and_maximum_modes() -> None:
    # SME minimum_count mode: count >= 4 -> 4, >= 2 -> 3, >= 1 -> 2, else 1
    sme_cfg = CountBandConfig(
        mode="minimum_count",
        threshold_4=4,
        threshold_3=2,
        threshold_2=1,
    )
    assert sme_cfg.mode == "minimum_count"
    assert sme_cfg.threshold_4 == 4
    assert sme_cfg.threshold_3 == 2
    assert sme_cfg.threshold_2 == 1

    # Invalid minimum_count (non-monotonic or non-positive)
    with pytest.raises(ValueError, match="strictly descending positive integers"):
        CountBandConfig(
            mode="minimum_count",
            threshold_4=4,
            threshold_3=2,
            threshold_2=0,
        )

    with pytest.raises(ValueError, match="strictly descending positive integers"):
        CountBandConfig(
            mode="minimum_count",
            threshold_4=4,
            threshold_3=4,
            threshold_2=2,
        )

    # GAD-01 maximum_count: count <= 0 -> 4, <= 1 -> 3, <= 3 -> 2, else 1
    gad01_cfg = CountBandConfig(
        mode="maximum_count",
        threshold_4=0,
        threshold_3=1,
        threshold_2=3,
    )
    assert gad01_cfg.mode == "maximum_count"
    assert gad01_cfg.threshold_4 == 0
    assert gad01_cfg.threshold_3 == 1
    assert gad01_cfg.threshold_2 == 3

    # GAD-03/04/05 maximum_count: count <= 0 -> 4, <= 2 -> 3, <= 5 -> 2, else 1
    gad_std_cfg = CountBandConfig(
        mode="maximum_count",
        threshold_4=0,
        threshold_3=2,
        threshold_2=5,
    )
    assert gad_std_cfg.threshold_4 == 0
    assert gad_std_cfg.threshold_3 == 2
    assert gad_std_cfg.threshold_2 == 5

    # Invalid maximum_count (non-monotonic ascending)
    with pytest.raises(ValueError, match="strictly ascending non-negative"):
        CountBandConfig(
            mode="maximum_count",
            threshold_4=2,
            threshold_3=1,
            threshold_2=5,
        )


def test_ratio_band_coverage_percentage_and_op01_short_sample() -> None:
    # Standard moderate scale: 80 / 50 / 20 (> 0)
    std_cfg = RatioBandConfig(
        mode="coverage_percentage",
        threshold_4=80.0,
        threshold_3=50.0,
        threshold_2=20.0,
    )
    assert std_cfg.threshold_4 == 80.0
    assert std_cfg.threshold_3 == 50.0
    assert std_cfg.threshold_2 == 20.0
    assert std_cfg.short_sample is None

    # Invalid non-monotonic or <= 0
    with pytest.raises(ValueError, match="strictly monotonic descending"):
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=0.0,
        )

    # OP-01 shape: 80/50/20 with short-sample override for <4 units
    op01_cfg = RatioBandConfig(
        mode="coverage_percentage",
        threshold_4=80.0,
        threshold_3=50.0,
        threshold_2=20.0,
        short_sample=ShortSampleConfig(
            min_units=4,
            max_issues_4=0,
            max_issues_3=1,
            max_issues_2=2,
        ),
    )
    assert op01_cfg.short_sample is not None
    assert op01_cfg.short_sample.min_units == 4
    assert op01_cfg.short_sample.max_issues_4 == 0
    assert op01_cfg.short_sample.max_issues_3 == 1
    assert op01_cfg.short_sample.max_issues_2 == 2


def test_ratio_band_absolute_difference_gad02() -> None:
    # GAD-02: difference <=2 => 4, <=5 => 3, <=10 => 2, else 1
    gad02_cfg = RatioBandConfig(
        mode="absolute_difference",
        threshold_4=2.0,
        threshold_3=5.0,
        threshold_2=10.0,
    )
    assert gad02_cfg.mode == "absolute_difference"
    assert gad02_cfg.threshold_4 == 2.0
    assert gad02_cfg.threshold_3 == 5.0
    assert gad02_cfg.threshold_2 == 10.0


def test_maximum_legal_llm_config_bounds_unreachable_oversize() -> None:
    # Maximum legal LLM config: max guidance (4000) and 4 max descriptors (2000 each)
    max_descriptors = tuple(
        LlmScoreDescriptor(score=s, descriptor="D" * MAX_DESCRIPTOR_LENGTH)
        for s in (1, 2, 3, 4)
    )
    max_cfg = LlmRubricGuidanceConfig(
        guidance="G" * MAX_GUIDANCE_LENGTH,
        level_descriptors=max_descriptors,
    )
    cfg_bytes = calculate_config_json_bytes(max_cfg)
    # Total chars: 4000 + 4 * 2000 = 12000 chars + JSON wrapper ~ 12.3 KB <= 16 KB
    assert cfg_bytes <= MAX_CONFIG_JSON_BYTES
    assert cfg_bytes > 12000


def test_finite_numeric_enforcement() -> None:
    with pytest.raises(ValueError, match="finite number"):
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=float("nan"),
            threshold_3=50.0,
            threshold_2=20.0,
        )


# ---------------------------------------------------------------------------
# Measurement DTO Tests
# ---------------------------------------------------------------------------


def test_grounded_score_measurement() -> None:
    dto = GroundedScoreMeasurement(
        score=4,
        evidence="Clear and accurate explanations throughout Chapter 2.",
        reasoning="All learning objectives were addressed.",
    )
    assert dto.score == 4
    assert dto.reasoning is not None


def test_qualifying_units_measurement_validation() -> None:
    u1 = GroundedUnit(
        unit_id="U-01",
        evidence="Objective 1 measured in Activity 1",
        label="Obj 1",
        location="Page 5",
    )
    u2 = GroundedUnit(
        unit_id="U-02",
        evidence="Objective 2 measured in Activity 2",
        label="Obj 2",
        location="Page 8",
    )
    u3 = GroundedUnit(
        unit_id="U-03",
        evidence="Objective 3 not aligned",
        label="Obj 3",
        location="Page 11",
    )

    dto = QualifyingUnitsMeasurement(
        total_units=(u1, u2, u3),
        qualifying_unit_ids=("U-01", "U-02"),
        summary="2 of 3 objectives aligned.",
    )
    assert dto.total_count == 3
    assert dto.qualifying_count == 2

    # Duplicate unit_id in total_units
    with pytest.raises(ValueError, match="Duplicate unit_id in total_units"):
        QualifyingUnitsMeasurement(
            total_units=(u1, u1),
            qualifying_unit_ids=("U-01",),
        )

    # Duplicate unit_id in qualifying_unit_ids
    with pytest.raises(ValueError, match="Duplicate unit_id in qualifying_unit_ids"):
        QualifyingUnitsMeasurement(
            total_units=(u1, u2),
            qualifying_unit_ids=("U-01", "U-01"),
        )

    # Qualifying unit ID not present in total_units
    with pytest.raises(ValueError, match="does not exist in total_units"):
        QualifyingUnitsMeasurement(
            total_units=(u1, u2),
            qualifying_unit_ids=("U-01", "U-99"),
        )

    # has_measurable_content=False cannot accompany non-empty total_units
    with pytest.raises(
        ValueError,
        match="has_measurable_content cannot be False when total_units is not empty",
    ):
        QualifyingUnitsMeasurement(
            total_units=(u1,),
            qualifying_unit_ids=(),
            has_measurable_content=False,
        )

    # has_measurable_content=False with empty total_units is valid
    empty_unmeasurable = QualifyingUnitsMeasurement(
        total_units=(),
        qualifying_unit_ids=(),
        has_measurable_content=False,
    )
    assert empty_unmeasurable.has_measurable_content is False
    assert empty_unmeasurable.total_count == 0


def test_frozen_contract_model_rejects_nan_and_inf() -> None:
    """Test that float fields on FrozenContractModel reject nan and inf."""
    with pytest.raises(ValidationError):
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=float("nan"),
            threshold_3=50.0,
            threshold_2=20.0,
        )

    with pytest.raises(ValidationError):
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=float("inf"),
            threshold_3=50.0,
            threshold_2=20.0,
        )


def test_canonicalize_form_orders_domains_and_criteria() -> None:
    c1 = _sample_criterion(code="B-01", display_order=1)
    c2 = _sample_criterion(code="A-01", display_order=0)

    d1 = _sample_domain(code="DOM-B", display_order=1, criteria=[c1, c2])
    d2 = _sample_domain(
        code="DOM-A",
        display_order=0,
        criteria=[_sample_criterion(code="Z-01", display_order=0)],
    )

    form = _sample_form(domains=[d1, d2])

    canonical = canonicalize_form(form)

    # Domains ordered by display_order
    assert [d.code for d in canonical.domains] == ["DOM-A", "DOM-B"]
    # Criteria inside DOM-B ordered by display_order
    dom_b = canonical.domains[1]
    assert [c.criterion_code for c in dom_b.criteria] == ["A-01", "B-01"]


def test_calculate_json_bytes() -> None:
    cfg = CountBandConfig(
        mode="minimum_count", threshold_4=4, threshold_3=3, threshold_2=2
    )
    cfg_bytes = calculate_config_json_bytes(cfg)
    assert 0 < cfg_bytes < MAX_CONFIG_JSON_BYTES

    form = _sample_form()
    form_bytes = calculate_form_json_bytes(form)
    assert 0 < form_bytes < MAX_FORM_JSON_BYTES
