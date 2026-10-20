"""Static capability manifests for this specialist."""

from equiped_harness.contracts.capabilities import (
    AgentCapabilityManifest,
    StrategyCapability,
)

SME_MANIFEST_V1 = AgentCapabilityManifest(
    agent_id="sme",
    adapter_key="sme",
    adapter_version=1,
    prompt_budget_setting="sme_total_prompt_budget_chars",
    supported_strategies=("llm_rubric_guidance", "count_band", "ratio_band"),
    supported_count_modes=("minimum_count",),
    supported_ratio_modes=("coverage_percentage",),
    capabilities=(
        StrategyCapability(
            strategy="llm_rubric_guidance",
            mode=None,
            measurement_shape="grounded_score",
        ),
        StrategyCapability(
            strategy="count_band",
            mode="minimum_count",
            measurement_shape="grounded_instances",
        ),
        StrategyCapability(
            strategy="ratio_band",
            mode="coverage_percentage",
            measurement_shape="qualifying_units",
        ),
    ),
    supported_measurement_shapes=(
        "grounded_score",
        "grounded_instances",
        "qualifying_units",
    ),
    min_criteria=1,
    max_criteria=20,
    default_prompt_budget_chars=15000,
)
