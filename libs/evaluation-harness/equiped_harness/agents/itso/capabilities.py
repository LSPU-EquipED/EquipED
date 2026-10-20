"""Static capability manifests for this specialist."""

from equiped_harness.contracts.capabilities import (
    AgentCapabilityManifest,
    StrategyCapability,
)

ITSO_MANIFEST_V1 = AgentCapabilityManifest(
    agent_id="itso",
    adapter_key="itso",
    adapter_version=1,
    prompt_budget_setting="agent_total_prompt_budget_chars",
    supported_strategies=("llm_rubric_guidance",),
    supported_count_modes=(),
    supported_ratio_modes=(),
    capabilities=(
        StrategyCapability(
            strategy="llm_rubric_guidance",
            mode=None,
            measurement_shape="grounded_score",
        ),
    ),
    supported_measurement_shapes=("grounded_score",),
    min_criteria=1,
    max_criteria=10,
    default_prompt_budget_chars=32000,
)

ITSO_MANIFEST_V2 = AgentCapabilityManifest(
    agent_id="itso",
    adapter_key="itso",
    adapter_version=2,
    prompt_budget_setting="agent_total_prompt_budget_chars",
    supported_strategies=("evidence_verification",),
    capabilities=(
        StrategyCapability(
            strategy="evidence_verification",
            measurement_shape="itso_evidence",
        ),
    ),
    supported_measurement_shapes=("itso_evidence",),
    min_criteria=5,
    max_criteria=5,
    default_prompt_budget_chars=32000,
    allowed_criterion_codes=("ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05"),
    required_criterion_strategies=tuple(
        (code, "evidence_verification")
        for code in ("ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05")
    ),
)

ITSO_MANIFEST_V3 = AgentCapabilityManifest(
    agent_id="itso",
    adapter_key="itso",
    adapter_version=3,
    prompt_budget_setting="agent_total_prompt_budget_chars",
    supported_strategies=("llm_rubric_guidance",),
    capabilities=(
        StrategyCapability(
            strategy="llm_rubric_guidance",
            measurement_shape="grounded_score",
        ),
    ),
    supported_measurement_shapes=("grounded_score",),
    min_criteria=5,
    max_criteria=5,
    default_prompt_budget_chars=32000,
    allowed_criterion_codes=("ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05"),
    required_criterion_strategies=tuple(
        (code, "llm_rubric_guidance")
        for code in ("ITSO-01", "ITSO-02", "ITSO-03", "ITSO-04", "ITSO-05")
    ),
)
