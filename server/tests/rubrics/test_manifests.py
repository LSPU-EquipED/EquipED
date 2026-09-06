"""Unit tests for capability manifests, resolver helpers, and pure validate_form."""

from __future__ import annotations

import uuid

import pytest
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
    ShortSampleConfig,
)
from server.modules.rubrics.manifests import (
    AGENT_MANIFEST_REGISTRY_V1,
    COORDINATOR_MANIFEST_V1,
    COORDINATOR_MANIFEST_V2,
    GAD_MANIFEST_V1,
    ITSO_MANIFEST_V1,
    SME_MANIFEST_V1,
    AgentCapabilityManifest,
    StrategyCapability,
    get_agent_manifest,
    resolve_criterion_measurement_shape,
    resolve_measurement_shape,
    validate_form,
)


def _make_criterion(
    code: str,
    title: str,
    strategy_config: (
        LlmRubricGuidanceConfig
        | CountBandConfig
        | RatioBandConfig
        | CurriculumAlignmentConfig
    ),
    display_order: int = 0,
    scoring_rule: str | None = "Standard scoring rule",
    criterion_id: uuid.UUID | None = None,
) -> CriterionDefinition:
    return CriterionDefinition(
        rubric_criterion_id=criterion_id or uuid.uuid4(),
        criterion_code=code,
        title=title,
        description=f"Description for {code}",
        scoring_rule=scoring_rule,
        display_order=display_order,
        strategy_config=strategy_config,
    )


# ---------------------------------------------------------------------------
# Complete Revision 1 Form Fixtures
# ---------------------------------------------------------------------------


def _full_sme_form() -> FormDefinition:
    """Complete 10-criterion Revision 1 form for Subject Matter Expert."""
    d1_criteria = (
        _make_criterion(
            "OP-01",
            "Topic Coherence",
            RatioBandConfig(
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
            ),
            display_order=0,
        ),
        _make_criterion(
            "OP-02",
            "Interactive Elements",
            CountBandConfig(
                mode="minimum_count",
                threshold_4=4,
                threshold_3=2,
                threshold_2=1,
            ),
            display_order=1,
        ),
        _make_criterion(
            "OP-03",
            "Clear Directions",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            display_order=2,
        ),
        _make_criterion(
            "OP-04",
            "Accurate Sections",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            display_order=3,
        ),
        _make_criterion(
            "OP-05",
            "Enhancement Activities",
            CountBandConfig(
                mode="minimum_count",
                threshold_4=3,
                threshold_3=2,
                threshold_2=1,
            ),
            display_order=4,
        ),
    )

    d2_criteria = (
        _make_criterion(
            "A-01",
            "Higher-Order Thinking Tasks",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            display_order=0,
        ),
        _make_criterion(
            "A-02",
            "Varied Assessment Types",
            CountBandConfig(
                mode="minimum_count",
                threshold_4=5,
                threshold_3=3,
                threshold_2=2,
            ),
            display_order=1,
        ),
        _make_criterion(
            "A-03",
            "Progress Monitoring",
            CountBandConfig(
                mode="minimum_count",
                threshold_4=4,
                threshold_3=2,
                threshold_2=1,
            ),
            display_order=2,
        ),
        _make_criterion(
            "A-04",
            "Prescriptive Feedback",
            CountBandConfig(
                mode="minimum_count",
                threshold_4=3,
                threshold_3=2,
                threshold_2=1,
            ),
            display_order=3,
        ),
        _make_criterion(
            "A-05",
            "Objective Gauging",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            display_order=4,
        ),
    )

    domain1 = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="OP",
        title="Operational Quality",
        display_order=0,
        criteria=d1_criteria,
    )
    domain2 = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="A",
        title="Assessment Quality",
        display_order=1,
        criteria=d2_criteria,
    )

    return FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        name="SME Revision 1",
        version_number=1,
        adapter_key="sme",
        adapter_version=1,
        domains=(domain1, domain2),
    )


def _full_gad_form() -> FormDefinition:
    """Complete 5-criterion Revision 1 form for Gender and Development."""
    criteria = (
        _make_criterion(
            "GAD-01",
            "Gender Stereotypes",
            CountBandConfig(
                mode="maximum_count",
                threshold_4=0,
                threshold_3=1,
                threshold_2=3,
            ),
            display_order=0,
        ),
        _make_criterion(
            "GAD-02",
            "Representation Balance",
            RatioBandConfig(
                mode="absolute_difference",
                threshold_4=2.0,
                threshold_3=5.0,
                threshold_2=10.0,
            ),
            display_order=1,
        ),
        _make_criterion(
            "GAD-03",
            "Gender Capability & Opportunity",
            CountBandConfig(
                mode="maximum_count",
                threshold_4=0,
                threshold_3=2,
                threshold_2=5,
            ),
            display_order=2,
        ),
        _make_criterion(
            "GAD-04",
            "Life Experiences & Responsibilities",
            CountBandConfig(
                mode="maximum_count",
                threshold_4=0,
                threshold_3=2,
                threshold_2=5,
            ),
            display_order=3,
        ),
        _make_criterion(
            "GAD-05",
            "Peace & Equality Content",
            CountBandConfig(
                mode="maximum_count",
                threshold_4=0,
                threshold_3=2,
                threshold_2=5,
            ),
            display_order=4,
        ),
    )

    domain = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="GAD_DOM",
        title="Gender and Development",
        display_order=0,
        criteria=criteria,
    )

    return FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="GAD Revision 1",
        version_number=1,
        adapter_key="gad",
        adapter_version=1,
        domains=(domain,),
    )


def _full_itso_form() -> FormDefinition:
    """Complete 5-criterion Revision 1 form for ITSO."""
    criteria = tuple(
        _make_criterion(
            f"ITSO-0{i}",
            f"ITSO Standard {i}",
            LlmRubricGuidanceConfig(guidance=f"Evaluate ITSO criterion {i}"),
            display_order=i - 1,
        )
        for i in range(1, 6)
    )

    domain = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="ITSO_DOM",
        title="ITSO Standards",
        display_order=0,
        criteria=criteria,
    )

    return FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="itso",
        name="ITSO Revision 1",
        version_number=1,
        adapter_key="itso",
        adapter_version=1,
        domains=(domain,),
    )


def _full_coordinator_form() -> FormDefinition:
    """Complete independent-scoring Coordinator form."""
    codes = (
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
    )
    criteria = tuple(
        _make_criterion(
            code,
            f"Criterion {code}",
            CurriculumAlignmentConfig(guidance="Evaluate syllabus alignment.")
            if code == "A-05"
            else LlmRubricGuidanceConfig(guidance=f"Evaluate {code}."),
            display_order=index,
        )
        for index, code in enumerate(codes)
    )
    domain = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="COORD",
        title="Coordinator Evaluation",
        display_order=0,
        criteria=criteria,
    )
    return FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="coordinator",
        name="Coordinator Revision 3",
        version_number=3,
        adapter_key="coordinator",
        adapter_version=2,
        domains=(domain,),
    )


# ---------------------------------------------------------------------------
# Capability Manifest Invariants Tests
# ---------------------------------------------------------------------------


def test_manifest_constants_properties() -> None:
    assert SME_MANIFEST_V1.agent_id == "sme"
    assert SME_MANIFEST_V1.prompt_budget_setting == "sme_total_prompt_budget_chars"
    assert SME_MANIFEST_V1.supported_count_modes == ("minimum_count",)
    assert SME_MANIFEST_V1.default_prompt_budget_chars == 15000
    assert SME_MANIFEST_V1.min_criteria == 1
    assert SME_MANIFEST_V1.max_criteria == 20

    assert GAD_MANIFEST_V1.agent_id == "gad"
    assert GAD_MANIFEST_V1.prompt_budget_setting == "agent_total_prompt_budget_chars"
    assert GAD_MANIFEST_V1.supported_count_modes == ("maximum_count",)
    assert GAD_MANIFEST_V1.supported_ratio_modes == ("absolute_difference",)
    assert GAD_MANIFEST_V1.max_criteria == 10

    assert ITSO_MANIFEST_V1.agent_id == "itso"
    assert ITSO_MANIFEST_V1.prompt_budget_setting == "agent_total_prompt_budget_chars"
    assert ITSO_MANIFEST_V1.supported_strategies == ("llm_rubric_guidance",)

    assert COORDINATOR_MANIFEST_V1.agent_id == "coordinator"
    assert COORDINATOR_MANIFEST_V1.adapter_version == 1
    assert COORDINATOR_MANIFEST_V1.allowed_criterion_codes == ("A-05",)
    assert COORDINATOR_MANIFEST_V1.max_criteria == 1

    assert COORDINATOR_MANIFEST_V2.adapter_version == 2
    assert (
        COORDINATOR_MANIFEST_V2.prompt_budget_setting
        == "agent_total_prompt_budget_chars"
    )
    assert COORDINATOR_MANIFEST_V2.allowed_criterion_codes == (
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
    )
    assert COORDINATOR_MANIFEST_V2.min_criteria == 10
    assert COORDINATOR_MANIFEST_V2.max_criteria == 10
    assert COORDINATOR_MANIFEST_V2.required_criterion_strategies == (
        ("A-05", "curriculum_alignment"),
    )
    assert AGENT_MANIFEST_REGISTRY_V1["coordinator"] is COORDINATOR_MANIFEST_V2
    assert get_agent_manifest("coordinator", 1) is COORDINATOR_MANIFEST_V1
    assert get_agent_manifest("coordinator", 2) is COORDINATOR_MANIFEST_V2


def test_manifest_invariant_rejections() -> None:
    with pytest.raises(ValueError, match="min_criteria .* cannot exceed max_criteria"):
        AgentCapabilityManifest(
            agent_id="test",
            adapter_key="test",
            adapter_version=1,
            prompt_budget_setting="test_setting",
            supported_strategies=("count_band",),
            supported_count_modes=("minimum_count",),
            capabilities=(
                StrategyCapability(
                    strategy="count_band",
                    mode="minimum_count",
                    measurement_shape="grounded_instances",
                ),
            ),
            supported_measurement_shapes=("grounded_instances",),
            min_criteria=10,
            max_criteria=2,
            default_prompt_budget_chars=1000,
        )
    # Missing capability mapping for a supported strategy
    with pytest.raises(ValueError, match="Missing capability mapping"):
        AgentCapabilityManifest(
            agent_id="test",
            adapter_key="test",
            adapter_version=1,
            prompt_budget_setting="test_setting",
            supported_strategies=("count_band", "llm_rubric_guidance"),
            supported_count_modes=("minimum_count",),
            capabilities=(
                StrategyCapability(
                    strategy="count_band",
                    mode="minimum_count",
                    measurement_shape="grounded_instances",
                ),
            ),
            supported_measurement_shapes=("grounded_instances",),
            min_criteria=1,
            max_criteria=10,
            default_prompt_budget_chars=1000,
        )

    # Unbacked listed measurement shape
    with pytest.raises(ValueError, match="has no corresponding capability mapping"):
        AgentCapabilityManifest(
            agent_id="test",
            adapter_key="test",
            adapter_version=1,
            prompt_budget_setting="test_setting",
            supported_strategies=("count_band",),
            supported_count_modes=("minimum_count",),
            capabilities=(
                StrategyCapability(
                    strategy="count_band",
                    mode="minimum_count",
                    measurement_shape="grounded_instances",
                ),
            ),
            supported_measurement_shapes=(
                "grounded_instances",
                "grounded_score",
            ),
            min_criteria=1,
            max_criteria=10,
            default_prompt_budget_chars=1000,
        )


# ---------------------------------------------------------------------------
# Measurement Shape Resolver Tests
# ---------------------------------------------------------------------------


def test_resolve_measurement_shape() -> None:
    # SME mappings
    assert (
        resolve_measurement_shape(SME_MANIFEST_V1, "llm_rubric_guidance")
        == "grounded_score"
    )
    assert (
        resolve_measurement_shape(SME_MANIFEST_V1, "count_band", mode="minimum_count")
        == "grounded_instances"
    )
    assert (
        resolve_measurement_shape(
            SME_MANIFEST_V1, "ratio_band", mode="coverage_percentage"
        )
        == "qualifying_units"
    )

    # GAD mappings
    assert (
        resolve_measurement_shape(GAD_MANIFEST_V1, "count_band", mode="maximum_count")
        == "grounded_instances"
    )
    assert (
        resolve_measurement_shape(
            GAD_MANIFEST_V1, "ratio_band", mode="absolute_difference"
        )
        == "paired_counts"
    )

    # ITSO mappings
    assert (
        resolve_measurement_shape(ITSO_MANIFEST_V1, "llm_rubric_guidance")
        == "grounded_score"
    )

    # Coordinator mappings
    assert (
        resolve_measurement_shape(COORDINATOR_MANIFEST_V1, "curriculum_alignment")
        == "curriculum_alignment"
    )

    # Incompatible strategy/mode
    with pytest.raises(ValueError, match="is not supported by manifest"):
        resolve_measurement_shape(
            SME_MANIFEST_V1, "ratio_band", mode="absolute_difference"
        )


def test_resolve_criterion_measurement_shape() -> None:
    sme_form = _full_sme_form()
    op01 = sme_form.domains[0].criteria[0]
    shape = resolve_criterion_measurement_shape(SME_MANIFEST_V1, op01)
    assert shape == "qualifying_units"

    op02 = sme_form.domains[0].criteria[1]
    shape_count = resolve_criterion_measurement_shape(SME_MANIFEST_V1, op02)
    assert shape_count == "grounded_instances"


# ---------------------------------------------------------------------------
# Full Revision 1 Form Validation Tests
# ---------------------------------------------------------------------------


def test_full_revision1_forms_pass_manifest_validation() -> None:
    sme_report = validate_form(_full_sme_form(), SME_MANIFEST_V1)
    assert sme_report.is_valid
    assert len(sme_report.errors) == 0
    assert sme_report.criteria_count == 10
    assert sme_report.estimated_prompt_chars > 0

    gad_report = validate_form(_full_gad_form(), GAD_MANIFEST_V1)
    assert gad_report.is_valid
    assert len(gad_report.errors) == 0
    assert gad_report.criteria_count == 5

    itso_report = validate_form(_full_itso_form(), ITSO_MANIFEST_V1)
    assert itso_report.is_valid
    assert len(itso_report.errors) == 0
    assert itso_report.criteria_count == 5

    coord_report = validate_form(_full_coordinator_form(), COORDINATOR_MANIFEST_V2)
    assert coord_report.is_valid
    assert len(coord_report.errors) == 0
    assert coord_report.criteria_count == 10


def test_coordinator_v2_requires_exactly_ten_criteria() -> None:
    form = _full_coordinator_form()
    domain = form.domains[0].model_copy(
        update={"criteria": form.domains[0].criteria[:-1]}
    )
    report = validate_form(
        form.model_copy(update={"domains": (domain,)}),
        COORDINATOR_MANIFEST_V2,
    )

    assert not report.is_valid
    assert any(i.code == "CRITERIA_COUNT_OUT_OF_BOUNDS" for i in report.errors)


def test_coordinator_v2_requires_curriculum_strategy_for_a05() -> None:
    form = _full_coordinator_form()
    criteria = tuple(
        criterion.model_copy(
            update={
                "strategy_config": LlmRubricGuidanceConfig(
                    guidance="Incorrect strategy for A-05."
                )
            }
        )
        if criterion.criterion_code == "A-05"
        else criterion
        for criterion in form.domains[0].criteria
    )
    domain = form.domains[0].model_copy(update={"criteria": criteria})
    report = validate_form(
        form.model_copy(update={"domains": (domain,)}),
        COORDINATOR_MANIFEST_V2,
    )

    assert not report.is_valid
    assert any(i.code == "REQUIRED_CRITERION_STRATEGY_MISMATCH" for i in report.errors)


# ---------------------------------------------------------------------------
# Count Mode & Short-Sample Incompatibility Tests
# ---------------------------------------------------------------------------


def test_validate_form_rejects_incompatible_count_mode() -> None:
    # SME attempting to use maximum_count mode
    bad_count = _make_criterion(
        "OP-02",
        "Interactive Elements",
        CountBandConfig(
            mode="maximum_count",
            threshold_4=0,
            threshold_3=2,
            threshold_2=5,
        ),
        display_order=0,
    )
    domain = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="DOM",
        title="Domain",
        display_order=0,
        criteria=(bad_count,),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        name="Bad SME Form",
        version_number=1,
        adapter_key="sme",
        adapter_version=1,
        domains=(domain,),
    )
    report = validate_form(form, SME_MANIFEST_V1)
    assert not report.is_valid
    assert any(i.code == "UNSUPPORTED_COUNT_MODE" for i in report.errors)


def test_sme_accepts_short_sample_on_novel_coverage_percentage_criteria() -> None:
    novel_ratio = _make_criterion(
        "NOVEL-RATIO-01",
        "Novel Ratio With Short Sample",
        RatioBandConfig(
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
        ),
        display_order=0,
    )
    domain = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="DOM",
        title="Domain",
        display_order=0,
        criteria=(novel_ratio,),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        name="Valid Novel SME Form With Short Sample",
        version_number=1,
        adapter_key="sme",
        adapter_version=1,
        domains=(domain,),
    )
    report = validate_form(form, SME_MANIFEST_V1)
    assert report.is_valid, f"Validation failed: {report.errors}"
    assert report.criteria_count == 1


def test_duplicate_domain_and_criterion_id_and_code_rejections() -> None:
    shared_domain_id = uuid.uuid4()
    c1 = _make_criterion(
        "C-01",
        "Crit 1",
        CountBandConfig(
            mode="minimum_count", threshold_4=4, threshold_3=3, threshold_2=2
        ),
        display_order=0,
    )
    c2 = _make_criterion(
        "C-02",
        "Crit 2",
        CountBandConfig(
            mode="minimum_count", threshold_4=4, threshold_3=3, threshold_2=2
        ),
        display_order=1,
    )

    d1 = DomainDefinition(
        rubric_domain_id=shared_domain_id,
        code="DOM-1",
        title="Domain 1",
        display_order=0,
        criteria=(c1,),
    )
    d2 = DomainDefinition(
        rubric_domain_id=shared_domain_id,
        code="DOM-1",
        title="Domain 2",
        display_order=1,
        criteria=(c2,),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        name="Duplicate Domain Form",
        version_number=1,
        adapter_key="sme",
        adapter_version=1,
        domains=(d1, d2),
    )
    report = validate_form(form, SME_MANIFEST_V1)
    assert not report.is_valid
    codes = {i.code for i in report.errors}
    assert "DUPLICATE_DOMAIN_ID" in codes
    assert "DUPLICATE_DOMAIN_CODE" in codes


def test_duplicate_criterion_id_and_code_across_domains() -> None:
    shared_criterion_id = uuid.uuid4()
    c1 = _make_criterion(
        "SHARED-01",
        "Crit 1",
        CountBandConfig(
            mode="minimum_count", threshold_4=4, threshold_3=3, threshold_2=2
        ),
        display_order=0,
        criterion_id=shared_criterion_id,
    )
    c2 = _make_criterion(
        "SHARED-01",
        "Crit 2",
        CountBandConfig(
            mode="minimum_count", threshold_4=4, threshold_3=3, threshold_2=2
        ),
        display_order=0,
        criterion_id=shared_criterion_id,
    )

    d1 = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="DOM-1",
        title="Domain 1",
        display_order=0,
        criteria=(c1,),
    )
    d2 = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="DOM-2",
        title="Domain 2",
        display_order=1,
        criteria=(c2,),
    )

    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        name="Duplicate Criterion Form",
        version_number=1,
        adapter_key="sme",
        adapter_version=1,
        domains=(d1, d2),
    )
    report = validate_form(form, SME_MANIFEST_V1)
    assert not report.is_valid
    codes = {i.code for i in report.errors}
    assert "DUPLICATE_CRITERION_ID" in codes
    assert "DUPLICATE_CRITERION_CODE" in codes


# ---------------------------------------------------------------------------
# Case-Insensitive Global Criterion Code Collision Tests
# ---------------------------------------------------------------------------


def test_case_insensitive_criterion_code_collision_rejection() -> None:
    c1 = _make_criterion(
        "CUSTOM-01",
        "Crit Upper",
        CountBandConfig(
            mode="minimum_count", threshold_4=4, threshold_3=3, threshold_2=2
        ),
        display_order=0,
    )
    c2 = _make_criterion(
        "custom-01",
        "Crit Lower",
        CountBandConfig(
            mode="minimum_count", threshold_4=4, threshold_3=3, threshold_2=2
        ),
        display_order=1,
    )

    d1 = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="DOM-1",
        title="Domain 1",
        display_order=0,
        criteria=(c1, c2),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        name="Case Collision Form",
        version_number=1,
        adapter_key="sme",
        adapter_version=1,
        domains=(d1,),
    )
    report = validate_form(form, SME_MANIFEST_V1)
    assert not report.is_valid
    assert any(
        i.code == "DUPLICATE_CRITERION_CODE" and "case-insensitive match" in i.message
        for i in report.errors
    )


def test_gad_case_only_criterion_code_collision_rejection() -> None:
    c1 = _make_criterion(
        "gad-01",
        "Gender Stereotypes Lower",
        CountBandConfig(
            mode="maximum_count",
            threshold_4=0,
            threshold_3=1,
            threshold_2=3,
        ),
        display_order=0,
    )
    c2 = _make_criterion(
        "GAD-01",
        "Gender Stereotypes Upper",
        CountBandConfig(
            mode="maximum_count",
            threshold_4=0,
            threshold_3=1,
            threshold_2=3,
        ),
        display_order=1,
    )
    domain = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="GAD_DOM",
        title="Gender and Development",
        display_order=0,
        criteria=(c1, c2),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="GAD Collision Form",
        version_number=1,
        adapter_key="gad",
        adapter_version=1,
        domains=(domain,),
    )
    report = validate_form(form, GAD_MANIFEST_V1)
    assert not report.is_valid
    assert any(
        i.code == "DUPLICATE_CRITERION_CODE" and "case-insensitive match" in i.message
        for i in report.errors
    )


# ---------------------------------------------------------------------------
# Novel Supported Criterion Codes & Unsupported Shapes Regressions
# ---------------------------------------------------------------------------


def test_novel_sme_criterion_codes_for_all_supported_shapes() -> None:
    c_guidance = _make_criterion(
        "NOVEL-SME-01",
        "Novel SME Guidance",
        LlmRubricGuidanceConfig(guidance="Evaluate custom pedagogical rigor."),
        display_order=0,
    )
    c_count = _make_criterion(
        "NOVEL-SME-02",
        "Novel SME Count",
        CountBandConfig(
            mode="minimum_count",
            threshold_4=5,
            threshold_3=3,
            threshold_2=1,
        ),
        display_order=1,
    )
    c_ratio = _make_criterion(
        "NOVEL-SME-03",
        "Novel SME Ratio",
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=85.0,
            threshold_3=60.0,
            threshold_2=30.0,
        ),
        display_order=2,
    )

    domain = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="NOVEL_SME_DOM",
        title="Novel SME Domain",
        display_order=0,
        criteria=(c_guidance, c_count, c_ratio),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        name="Novel SME Form",
        version_number=1,
        adapter_key="sme",
        adapter_version=1,
        domains=(domain,),
    )

    report = validate_form(form, SME_MANIFEST_V1)
    assert report.is_valid, f"Validation failed: {report.errors}"
    assert report.criteria_count == 3

    assert (
        resolve_criterion_measurement_shape(SME_MANIFEST_V1, c_guidance)
        == "grounded_score"
    )
    assert (
        resolve_criterion_measurement_shape(SME_MANIFEST_V1, c_count)
        == "grounded_instances"
    )
    assert (
        resolve_criterion_measurement_shape(SME_MANIFEST_V1, c_ratio)
        == "qualifying_units"
    )


def test_novel_gad_criterion_codes_for_all_supported_shapes() -> None:
    c_count = _make_criterion(
        "NOVEL-GAD-01",
        "Novel GAD Max Count",
        CountBandConfig(
            mode="maximum_count",
            threshold_4=0,
            threshold_3=1,
            threshold_2=2,
        ),
        display_order=0,
    )
    c_ratio = _make_criterion(
        "NOVEL-GAD-02",
        "Novel GAD Diff Ratio",
        RatioBandConfig(
            mode="absolute_difference",
            threshold_4=1.0,
            threshold_3=3.0,
            threshold_2=6.0,
        ),
        display_order=1,
    )

    domain = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="NOVEL_GAD_DOM",
        title="Novel GAD Domain",
        display_order=0,
        criteria=(c_count, c_ratio),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="Novel GAD Form",
        version_number=1,
        adapter_key="gad",
        adapter_version=1,
        domains=(domain,),
    )

    report = validate_form(form, GAD_MANIFEST_V1)
    assert report.is_valid, f"Validation failed: {report.errors}"
    assert report.criteria_count == 2

    assert (
        resolve_criterion_measurement_shape(GAD_MANIFEST_V1, c_count)
        == "grounded_instances"
    )
    assert (
        resolve_criterion_measurement_shape(GAD_MANIFEST_V1, c_ratio) == "paired_counts"
    )


def test_novel_itso_criterion_code_with_guidance() -> None:
    c_guidance = _make_criterion(
        "NOVEL-ITSO-01",
        "Novel ITSO Guidance",
        LlmRubricGuidanceConfig(guidance="Evaluate novel cybersecurity standard."),
        display_order=0,
    )

    domain = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="NOVEL_ITSO_DOM",
        title="Novel ITSO Domain",
        display_order=0,
        criteria=(c_guidance,),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="itso",
        name="Novel ITSO Form",
        version_number=1,
        adapter_key="itso",
        adapter_version=1,
        domains=(domain,),
    )

    report = validate_form(form, ITSO_MANIFEST_V1)
    assert report.is_valid, f"Validation failed: {report.errors}"
    assert report.criteria_count == 1
    assert (
        resolve_criterion_measurement_shape(ITSO_MANIFEST_V1, c_guidance)
        == "grounded_score"
    )


def test_coordinator_rejects_novel_criterion_code() -> None:
    c_novel = _make_criterion(
        "NOVEL-COORD-01",
        "Novel Coordinator Code",
        CurriculumAlignmentConfig(guidance="Evaluate syllabus alignment."),
        display_order=0,
    )

    domain = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="CURR_ALIGN",
        title="Curriculum Alignment",
        display_order=0,
        criteria=(c_novel,),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="coordinator",
        name="Novel Coordinator Form",
        version_number=2,
        adapter_key="coordinator",
        adapter_version=1,
        domains=(domain,),
    )

    report = validate_form(form, COORDINATOR_MANIFEST_V1)
    assert not report.is_valid
    assert any(i.code == "UNSUPPORTED_CRITERION_CODE" for i in report.errors)


def test_unsupported_shapes_and_strategies_for_agents() -> None:
    # GAD does not support llm_rubric_guidance
    c_gad_bad = _make_criterion(
        "GAD-BAD-01",
        "Bad GAD Guidance",
        LlmRubricGuidanceConfig(guidance="Invalid for GAD"),
        display_order=0,
    )
    d_gad = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="DOM",
        title="Domain",
        display_order=0,
        criteria=(c_gad_bad,),
    )
    f_gad = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="Bad GAD Form",
        version_number=1,
        adapter_key="gad",
        adapter_version=1,
        domains=(d_gad,),
    )
    report_gad = validate_form(f_gad, GAD_MANIFEST_V1)
    assert not report_gad.is_valid
    assert any(i.code == "UNSUPPORTED_STRATEGY" for i in report_gad.errors)

    # GAD does not support coverage_percentage ratio mode
    c_gad_bad_ratio = _make_criterion(
        "GAD-BAD-02",
        "Bad GAD Ratio Mode",
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80.0,
            threshold_3=50.0,
            threshold_2=20.0,
        ),
        display_order=0,
    )
    d_gad2 = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="DOM",
        title="Domain",
        display_order=0,
        criteria=(c_gad_bad_ratio,),
    )
    f_gad2 = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="Bad GAD Form 2",
        version_number=1,
        adapter_key="gad",
        adapter_version=1,
        domains=(d_gad2,),
    )
    report_gad2 = validate_form(f_gad2, GAD_MANIFEST_V1)
    assert not report_gad2.is_valid
    assert any(i.code == "UNSUPPORTED_RATIO_MODE" for i in report_gad2.errors)

    # ITSO does not support count_band
    c_itso_bad = _make_criterion(
        "ITSO-BAD-01",
        "Bad ITSO Count",
        CountBandConfig(
            mode="minimum_count",
            threshold_4=5,
            threshold_3=3,
            threshold_2=1,
        ),
        display_order=0,
    )
    d_itso = DomainDefinition(
        rubric_domain_id=uuid.uuid4(),
        code="DOM",
        title="Domain",
        display_order=0,
        criteria=(c_itso_bad,),
    )
    f_itso = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="itso",
        name="Bad ITSO Form",
        version_number=1,
        adapter_key="itso",
        adapter_version=1,
        domains=(d_itso,),
    )
    report_itso = validate_form(f_itso, ITSO_MANIFEST_V1)
    assert not report_itso.is_valid
    assert any(i.code == "UNSUPPORTED_STRATEGY" for i in report_itso.errors)


# ---------------------------------------------------------------------------
# Centralized Agent Manifest Registry Tests
# ---------------------------------------------------------------------------


def test_agent_manifest_registry_v1_coverage_and_immutability():
    expected_agents = {"sme", "gad", "itso", "coordinator"}
    assert set(AGENT_MANIFEST_REGISTRY_V1.keys()) == expected_agents

    assert AGENT_MANIFEST_REGISTRY_V1["sme"] == SME_MANIFEST_V1
    assert AGENT_MANIFEST_REGISTRY_V1["gad"] == GAD_MANIFEST_V1
    assert AGENT_MANIFEST_REGISTRY_V1["itso"] == ITSO_MANIFEST_V1
    assert AGENT_MANIFEST_REGISTRY_V1["coordinator"] == COORDINATOR_MANIFEST_V2

    # Immutable mapping proxy prevents mutation
    with pytest.raises(TypeError):
        AGENT_MANIFEST_REGISTRY_V1["sme"] = GAD_MANIFEST_V1  # type: ignore[index]


def test_get_agent_manifest_success_and_unknown_failure():
    assert get_agent_manifest("sme") == SME_MANIFEST_V1
    assert get_agent_manifest("gad") == GAD_MANIFEST_V1
    assert get_agent_manifest("itso") == ITSO_MANIFEST_V1
    assert get_agent_manifest("coordinator") == COORDINATOR_MANIFEST_V2

    with pytest.raises(
        ValueError, match="Unknown agent capability manifest for 'unknown'"
    ):
        get_agent_manifest("unknown")


def test_no_duplicate_public_manifest_registry_remains():
    import server.modules.rubrics as pkg
    import server.modules.rubrics.repository as repo
    import server.modules.rubrics.snapshot_contracts as snap

    assert not hasattr(repo, "MANIFEST_BY_AGENT")
    assert not hasattr(snap, "MANIFEST_BY_AGENT")
    assert not hasattr(snap, "get_manifest")
    assert not hasattr(pkg, "get_manifest")


# ---------------------------------------------------------------------------
# Coordinator Manifest V2 Full Capability Tests
# ---------------------------------------------------------------------------


def test_coordinator_manifest_supports_ten_criteria_and_four_strategies():
    """Verify coordinator manifest expanded to 10 criteria and 4 strategies."""
    CODES = (
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
    )
    m = get_agent_manifest("coordinator")
    assert m.adapter_version == 2
    assert m.min_criteria == 10
    assert m.max_criteria == 10
    assert set(m.allowed_criterion_codes) == set(CODES)
    assert set(m.supported_strategies) == {
        "curriculum_alignment",
        "llm_rubric_guidance",
        "count_band",
        "ratio_band",
    }
    shapes = {c.measurement_shape for c in m.capabilities}
    assert "curriculum_alignment" in shapes
    assert "grounded_instances" in shapes
    assert "qualifying_units" in shapes
    assert "grounded_score" in shapes
