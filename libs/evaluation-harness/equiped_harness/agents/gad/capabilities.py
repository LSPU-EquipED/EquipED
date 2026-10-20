"""Static capability manifests for this specialist."""

from equiped_harness.contracts.capabilities import (
    AgentCapabilityManifest,
    StrategyCapability,
)

GAD_MANIFEST_V1 = AgentCapabilityManifest(
    agent_id="gad",
    adapter_key="gad",
    adapter_version=1,
    prompt_budget_setting="agent_total_prompt_budget_chars",
    supported_strategies=("count_band", "ratio_band"),
    supported_count_modes=("maximum_count",),
    supported_ratio_modes=("absolute_difference",),
    capabilities=(
        StrategyCapability(
            strategy="count_band",
            mode="maximum_count",
            measurement_shape="grounded_instances",
        ),
        StrategyCapability(
            strategy="ratio_band",
            mode="absolute_difference",
            measurement_shape="paired_counts",
        ),
    ),
    supported_measurement_shapes=(
        "grounded_instances",
        "paired_counts",
    ),
    min_criteria=1,
    max_criteria=10,
    default_prompt_budget_chars=32000,
)

GAD_MANIFEST_V2 = AgentCapabilityManifest(
    agent_id="gad",
    adapter_key="gad",
    adapter_version=2,
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
