"""Pure capability manifests and validation logic for evaluation forms."""

from __future__ import annotations

import json
from types import MappingProxyType
from typing import Any

from pydantic import Field, field_validator, model_validator

from .contracts import (
    MAX_CODE_LENGTH,
    MAX_FORM_JSON_BYTES,
    CountBandConfig,
    CriterionDefinition,
    FormDefinition,
    FrozenContractModel,
    RatioBandConfig,
    ValidationIssue,
    ValidationReport,
    _clean_non_empty_str,
    _clean_optional_str,
    calculate_form_json_bytes,
)

# ---------------------------------------------------------------------------
# Capability Mapping Models
# ---------------------------------------------------------------------------


class StrategyCapability(FrozenContractModel):
    """Capability mapping a strategy and optional mode to a measurement shape."""

    strategy: str
    mode: str | None = None
    measurement_shape: str

    @field_validator("strategy")
    @classmethod
    def _validate_strategy(cls, value: str) -> str:
        return _clean_non_empty_str(value, "strategy", MAX_CODE_LENGTH)

    @field_validator("measurement_shape")
    @classmethod
    def _validate_shape(cls, value: str) -> str:
        return _clean_non_empty_str(value, "measurement_shape", MAX_CODE_LENGTH)

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "mode", MAX_CODE_LENGTH)


# ---------------------------------------------------------------------------
# Capability Manifest Definition
# ---------------------------------------------------------------------------


class AgentCapabilityManifest(FrozenContractModel):
    """Pure, immutable capability manifest defining an agent's form constraints."""

    agent_id: str
    adapter_key: str
    adapter_version: int
    prompt_budget_setting: str
    supported_strategies: tuple[str, ...]
    supported_count_modes: tuple[str, ...] = ()
    supported_ratio_modes: tuple[str, ...] = ()
    capabilities: tuple[StrategyCapability, ...] = ()
    supported_measurement_shapes: tuple[str, ...] = ()
    min_criteria: int = Field(..., ge=1)
    max_criteria: int = Field(..., ge=1)
    default_prompt_budget_chars: int = Field(..., gt=0)
    allowed_criterion_codes: tuple[str, ...] | None = None
    required_criterion_strategies: tuple[tuple[str, str], ...] = ()

    @field_validator(
        "supported_strategies",
        "supported_count_modes",
        "supported_ratio_modes",
        "capabilities",
        "supported_measurement_shapes",
        "allowed_criterion_codes",
        "required_criterion_strategies",
        mode="before",
    )
    @classmethod
    def _convert_to_tuple(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (list, tuple, set)):
            return tuple(value)
        return value

    @field_validator("prompt_budget_setting")
    @classmethod
    def _validate_prompt_budget_setting(cls, value: str) -> str:
        return _clean_non_empty_str(value, "prompt_budget_setting", MAX_CODE_LENGTH)

    @model_validator(mode="after")
    def _validate_manifest_invariants(self) -> AgentCapabilityManifest:
        if self.min_criteria > self.max_criteria:
            raise ValueError(
                f"min_criteria ({self.min_criteria}) cannot exceed "
                f"max_criteria ({self.max_criteria})"
            )

        if len(self.supported_strategies) != len(set(self.supported_strategies)):
            raise ValueError("supported_strategies must not contain duplicates")

        if len(self.supported_count_modes) != len(set(self.supported_count_modes)):
            raise ValueError("supported_count_modes must not contain duplicates")

        if len(self.supported_ratio_modes) != len(set(self.supported_ratio_modes)):
            raise ValueError("supported_ratio_modes must not contain duplicates")

        if len(self.supported_measurement_shapes) != len(
            set(self.supported_measurement_shapes)
        ):
            raise ValueError("supported_measurement_shapes must not contain duplicates")
        if self.allowed_criterion_codes is not None:
            if len(self.allowed_criterion_codes) != len(
                set(self.allowed_criterion_codes)
            ):
                raise ValueError("allowed_criterion_codes must not contain duplicates")

        required_codes: set[str] = set()
        for code, strategy in self.required_criterion_strategies:
            if code in required_codes:
                raise ValueError(
                    "required_criterion_strategies must not contain duplicate codes"
                )
            required_codes.add(code)
            if (
                self.allowed_criterion_codes is not None
                and code not in self.allowed_criterion_codes
            ):
                raise ValueError(
                    f"Required criterion code '{code}' is not in "
                    "allowed_criterion_codes"
                )
            if strategy not in self.supported_strategies:
                raise ValueError(f"Required strategy '{strategy}' is not supported")

        seen_pairs: set[tuple[str, str | None]] = set()
        capability_shapes: set[str] = set()

        for cap in self.capabilities:
            pair = (cap.strategy, cap.mode)
            if pair in seen_pairs:
                raise ValueError(
                    f"Duplicate capability mapping for strategy '{cap.strategy}' "
                    f"and mode '{cap.mode}'"
                )
            seen_pairs.add(pair)
            capability_shapes.add(cap.measurement_shape)

            if cap.strategy not in self.supported_strategies:
                raise ValueError(
                    f"Capability strategy '{cap.strategy}' not in "
                    f"supported_strategies {self.supported_strategies}"
                )
            if cap.strategy == "count_band" and cap.mode is not None:
                if cap.mode not in self.supported_count_modes:
                    raise ValueError(
                        f"Capability count mode '{cap.mode}' not in "
                        f"supported_count_modes {self.supported_count_modes}"
                    )
            if cap.strategy == "ratio_band" and cap.mode is not None:
                if cap.mode not in self.supported_ratio_modes:
                    raise ValueError(
                        f"Capability ratio mode '{cap.mode}' not in "
                        f"supported_ratio_modes {self.supported_ratio_modes}"
                    )
            if cap.measurement_shape not in self.supported_measurement_shapes:
                raise ValueError(
                    f"Capability measurement shape '{cap.measurement_shape}' not "
                    "in supported_measurement_shapes "
                    f"{self.supported_measurement_shapes}"
                )

        # Ensure no unbacked measurement shapes listed
        for shape in self.supported_measurement_shapes:
            if shape not in capability_shapes:
                raise ValueError(
                    f"Listed measurement shape '{shape}' has no corresponding "
                    "capability mapping"
                )

        # Check capabilities cover all supported strategies
        for strat in self.supported_strategies:
            if strat == "count_band":
                for mode in self.supported_count_modes:
                    if (strat, mode) not in seen_pairs:
                        raise ValueError(
                            f"Missing capability mapping for count_band mode '{mode}'"
                        )
            elif strat == "ratio_band":
                for mode in self.supported_ratio_modes:
                    if (strat, mode) not in seen_pairs:
                        raise ValueError(
                            f"Missing capability mapping for ratio_band mode '{mode}'"
                        )
            else:
                if (strat, None) not in seen_pairs:
                    raise ValueError(
                        f"Missing capability mapping for strategy '{strat}'"
                    )

        return self


# ---------------------------------------------------------------------------
# Exact Manifest Constants (V1)
# ---------------------------------------------------------------------------

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

COORDINATOR_MANIFEST_V1 = AgentCapabilityManifest(
    agent_id="coordinator",
    adapter_key="coordinator",
    adapter_version=1,
    prompt_budget_setting="agent_total_prompt_budget_chars",
    supported_strategies=("curriculum_alignment",),
    capabilities=(
        StrategyCapability(
            strategy="curriculum_alignment",
            mode=None,
            measurement_shape="curriculum_alignment",
        ),
    ),
    supported_measurement_shapes=("curriculum_alignment",),
    min_criteria=1,
    max_criteria=1,
    default_prompt_budget_chars=32000,
    allowed_criterion_codes=("A-05",),
    required_criterion_strategies=(("A-05", "curriculum_alignment"),),
)

COORDINATOR_MANIFEST_V2 = AgentCapabilityManifest(
    agent_id="coordinator",
    adapter_key="coordinator",
    adapter_version=2,
    prompt_budget_setting="agent_total_prompt_budget_chars",
    supported_strategies=(
        "curriculum_alignment",
        "llm_rubric_guidance",
        "count_band",
        "ratio_band",
    ),
    supported_count_modes=("minimum_count",),
    supported_ratio_modes=("coverage_percentage",),
    capabilities=(
        StrategyCapability(
            strategy="curriculum_alignment",
            mode=None,
            measurement_shape="curriculum_alignment",
        ),
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
        "curriculum_alignment",
        "grounded_score",
        "grounded_instances",
        "qualifying_units",
    ),
    min_criteria=10,
    max_criteria=10,
    default_prompt_budget_chars=32000,
    allowed_criterion_codes=(
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
    ),
    required_criterion_strategies=(("A-05", "curriculum_alignment"),),
)

AGENT_MANIFEST_REGISTRY_V1: MappingProxyType[str, AgentCapabilityManifest] = (
    MappingProxyType(
        {
            "sme": SME_MANIFEST_V1,
            "gad": GAD_MANIFEST_V1,
            "itso": ITSO_MANIFEST_V1,
            "coordinator": COORDINATOR_MANIFEST_V2,
        }
    )
)

AGENT_MANIFEST_VERSION_REGISTRY: MappingProxyType[
    tuple[str, int], AgentCapabilityManifest
] = MappingProxyType(
    {
        ("sme", 1): SME_MANIFEST_V1,
        ("gad", 1): GAD_MANIFEST_V1,
        ("itso", 1): ITSO_MANIFEST_V1,
        ("coordinator", 1): COORDINATOR_MANIFEST_V1,
        ("coordinator", 2): COORDINATOR_MANIFEST_V2,
    }
)


def get_agent_manifest(
    agent_id: str, adapter_version: int | None = None
) -> AgentCapabilityManifest:
    """Lookup the current or an exact historical agent manifest."""
    manifest = (
        AGENT_MANIFEST_REGISTRY_V1.get(agent_id)
        if adapter_version is None
        else AGENT_MANIFEST_VERSION_REGISTRY.get((agent_id, adapter_version))
    )
    if manifest is None:
        suffix = (
            "" if adapter_version is None else f" adapter version {adapter_version}"
        )
        raise ValueError(f"Unknown agent capability manifest for '{agent_id}'{suffix}")
    return manifest


# ---------------------------------------------------------------------------
# Measurement Shape Resolver Helper
# ---------------------------------------------------------------------------


def resolve_measurement_shape(
    manifest: AgentCapabilityManifest,
    strategy: str,
    mode: str | None = None,
) -> str:
    """Pure helper to resolve the measurement shape for a strategy/mode pair."""
    for cap in manifest.capabilities:
        if cap.strategy == strategy and cap.mode == mode:
            return cap.measurement_shape
    mode_str = f" with mode '{mode}'" if mode else ""
    raise ValueError(
        f"Strategy '{strategy}'{mode_str} is not supported by manifest "
        f"for '{manifest.agent_id}'"
    )


def resolve_criterion_measurement_shape(
    manifest: AgentCapabilityManifest,
    criterion: CriterionDefinition,
) -> str:
    """Pure helper to resolve the measurement shape for a CriterionDefinition."""
    strategy = criterion.strategy_config.strategy
    if isinstance(criterion.strategy_config, (CountBandConfig, RatioBandConfig)):
        mode = criterion.strategy_config.mode
    else:
        mode = None
    return resolve_measurement_shape(manifest, strategy, mode)


# ---------------------------------------------------------------------------
# Prompt Contribution Estimation
# ---------------------------------------------------------------------------


def estimate_prompt_budget_contribution(form: FormDefinition) -> int:
    """Estimate prompt character contribution for the form's criteria.

    Calculates criterion metadata text plus deterministic JSON config string.
    """
    total_chars = 0
    for domain in form.domains:
        total_chars += len(domain.code) + len(domain.title)
        for criterion in domain.criteria:
            total_chars += len(criterion.criterion_code)
            total_chars += len(criterion.title)
            total_chars += len(criterion.description)
            if criterion.scoring_rule:
                total_chars += len(criterion.scoring_rule)
            # Deterministic config JSON contribution
            config_payload = criterion.strategy_config.model_dump(mode="json")
            config_str = json.dumps(
                config_payload, sort_keys=True, separators=(",", ":")
            )
            total_chars += len(config_str)
    return total_chars


# ---------------------------------------------------------------------------
# Pure Form Validation
# ---------------------------------------------------------------------------


def validate_form(
    form: FormDefinition,
    manifest: AgentCapabilityManifest,
    *,
    prompt_budget_chars: int | None = None,
) -> ValidationReport:
    """Purely validate a FormDefinition against an AgentCapabilityManifest."""
    issues: list[ValidationIssue] = []

    # 1. Agent and adapter compatibility
    if form.agent_id != manifest.agent_id:
        issues.append(
            ValidationIssue(
                path="agent_id",
                code="AGENT_MISMATCH",
                message=(
                    f"Form agent_id '{form.agent_id}' does not match "
                    f"manifest agent_id '{manifest.agent_id}'"
                ),
            )
        )

    if form.adapter_key != manifest.adapter_key:
        issues.append(
            ValidationIssue(
                path="adapter_key",
                code="ADAPTER_KEY_MISMATCH",
                message=(
                    f"Form adapter_key '{form.adapter_key}' does not match "
                    f"manifest adapter_key '{manifest.adapter_key}'"
                ),
            )
        )

    if form.adapter_version != manifest.adapter_version:
        issues.append(
            ValidationIssue(
                path="adapter_version",
                code="ADAPTER_VERSION_MISMATCH",
                message=(
                    f"Form adapter_version {form.adapter_version} does not match "
                    f"manifest adapter_version {manifest.adapter_version}"
                ),
            )
        )

    # 2. Domain uniqueness checks
    seen_domain_ids: set[Any] = set()
    seen_domain_codes: set[str] = set()
    seen_domain_orders: set[int] = set()

    seen_criterion_ids: set[Any] = set()
    seen_criterion_codes: set[str] = set()
    seen_criterion_codes_casefolded: dict[str, str] = {}

    total_criteria = 0
    required_strategies = dict(manifest.required_criterion_strategies)
    for d_idx, domain in enumerate(form.domains):
        d_path = f"domains[{d_idx}]"
        if domain.rubric_domain_id in seen_domain_ids:
            issues.append(
                ValidationIssue(
                    path=f"{d_path}.rubric_domain_id",
                    code="DUPLICATE_DOMAIN_ID",
                    message=f"Duplicate domain ID '{domain.rubric_domain_id}'",
                )
            )
        seen_domain_ids.add(domain.rubric_domain_id)

        if domain.code in seen_domain_codes:
            issues.append(
                ValidationIssue(
                    path=f"{d_path}.code",
                    code="DUPLICATE_DOMAIN_CODE",
                    message=f"Duplicate domain code '{domain.code}'",
                )
            )
        seen_domain_codes.add(domain.code)

        if domain.display_order in seen_domain_orders:
            issues.append(
                ValidationIssue(
                    path=f"{d_path}.display_order",
                    code="DUPLICATE_DOMAIN_ORDER",
                    message=f"Duplicate domain display_order {domain.display_order}",
                )
            )
        seen_domain_orders.add(domain.display_order)

        # Intra-domain criterion display_order tracking
        seen_criteria_orders_in_domain: set[int] = set()

        for c_idx, criterion in enumerate(domain.criteria):
            total_criteria += 1
            c_path = f"{d_path}.criteria[{c_idx}]"

            if criterion.rubric_criterion_id in seen_criterion_ids:
                issues.append(
                    ValidationIssue(
                        path=f"{c_path}.rubric_criterion_id",
                        code="DUPLICATE_CRITERION_ID",
                        message=(
                            f"Duplicate criterion ID '{criterion.rubric_criterion_id}'"
                        ),
                    )
                )
            seen_criterion_ids.add(criterion.rubric_criterion_id)

            code_casefolded = criterion.criterion_code.casefold()
            if criterion.criterion_code in seen_criterion_codes:
                issues.append(
                    ValidationIssue(
                        path=f"{c_path}.criterion_code",
                        code="DUPLICATE_CRITERION_CODE",
                        message=(
                            f"Duplicate criterion code '{criterion.criterion_code}'"
                        ),
                    )
                )
            elif code_casefolded in seen_criterion_codes_casefolded:
                prev_code = seen_criterion_codes_casefolded[code_casefolded]
                issues.append(
                    ValidationIssue(
                        path=f"{c_path}.criterion_code",
                        code="DUPLICATE_CRITERION_CODE",
                        message=(
                            f"Duplicate criterion code '{criterion.criterion_code}' "
                            f"(case-insensitive match with '{prev_code}')"
                        ),
                    )
                )
            seen_criterion_codes.add(criterion.criterion_code)
            seen_criterion_codes_casefolded.setdefault(
                code_casefolded, criterion.criterion_code
            )

            if criterion.display_order in seen_criteria_orders_in_domain:
                issues.append(
                    ValidationIssue(
                        path=f"{c_path}.display_order",
                        code="DUPLICATE_CRITERION_ORDER",
                        message=(
                            f"Duplicate criterion display_order "
                            f"{criterion.display_order} in domain '{domain.code}'"
                        ),
                    )
                )
            seen_criteria_orders_in_domain.add(criterion.display_order)

            # Strategy compatibility
            strategy = criterion.strategy_config.strategy
            if strategy not in manifest.supported_strategies:
                issues.append(
                    ValidationIssue(
                        path=f"{c_path}.strategy_config.strategy",
                        code="UNSUPPORTED_STRATEGY",
                        message=(
                            f"Strategy '{strategy}' is not supported by manifest "
                            f"for '{manifest.agent_id}'. Supported: "
                            f"{manifest.supported_strategies}"
                        ),
                    )
                )

            # Mode compatibility for count_band
            if isinstance(criterion.strategy_config, CountBandConfig):
                mode = criterion.strategy_config.mode
                if mode not in manifest.supported_count_modes:
                    issues.append(
                        ValidationIssue(
                            path=f"{c_path}.strategy_config.mode",
                            code="UNSUPPORTED_COUNT_MODE",
                            message=(
                                f"Count mode '{mode}' is not supported by manifest "
                                f"for '{manifest.agent_id}'. Supported: "
                                f"{manifest.supported_count_modes}"
                            ),
                        )
                    )

            # Mode compatibility for ratio_band
            if isinstance(criterion.strategy_config, RatioBandConfig):
                mode = criterion.strategy_config.mode
                if mode not in manifest.supported_ratio_modes:
                    issues.append(
                        ValidationIssue(
                            path=f"{c_path}.strategy_config.mode",
                            code="UNSUPPORTED_RATIO_MODE",
                            message=(
                                f"Ratio mode '{mode}' is not supported by manifest "
                                f"for '{manifest.agent_id}'. Supported: "
                                f"{manifest.supported_ratio_modes}"
                            ),
                        )
                    )

            # Allowed criterion codes restriction
            if manifest.allowed_criterion_codes is not None:
                if criterion.criterion_code not in manifest.allowed_criterion_codes:
                    issues.append(
                        ValidationIssue(
                            path=f"{c_path}.criterion_code",
                            code="UNSUPPORTED_CRITERION_CODE",
                            message=(
                                f"Criterion code '{criterion.criterion_code}' "
                                f"is not allowed for '{manifest.agent_id}'. "
                                f"Allowed: {manifest.allowed_criterion_codes}"
                            ),
                        )
                    )
            required_strategy = required_strategies.get(criterion.criterion_code)
            if required_strategy is not None and strategy != required_strategy:
                issues.append(
                    ValidationIssue(
                        path=f"{c_path}.strategy_config.strategy",
                        code="REQUIRED_CRITERION_STRATEGY_MISMATCH",
                        message=(
                            f"Criterion '{criterion.criterion_code}' must use strategy "
                            f"'{required_strategy}', got '{strategy}'"
                        ),
                    )
                )
    # 3. Criteria count bounds
    if total_criteria < manifest.min_criteria or total_criteria > manifest.max_criteria:
        issues.append(
            ValidationIssue(
                path="domains.criteria",
                code="CRITERIA_COUNT_OUT_OF_BOUNDS",
                message=(
                    f"Total criteria count {total_criteria} outside allowed range "
                    f"[{manifest.min_criteria}, {manifest.max_criteria}] for "
                    f"'{manifest.agent_id}'"
                ),
            )
        )

    # 4. Form serialized JSON size check
    form_bytes = calculate_form_json_bytes(form)
    if form_bytes > MAX_FORM_JSON_BYTES:
        issues.append(
            ValidationIssue(
                path="form",
                code="FORM_SIZE_EXCEEDED",
                message=(
                    f"Serialized form size {form_bytes} bytes exceeds maximum "
                    f"allowed {MAX_FORM_JSON_BYTES} bytes"
                ),
            )
        )

    # 5. Prompt budget contribution check
    budget = (
        prompt_budget_chars
        if prompt_budget_chars is not None
        else manifest.default_prompt_budget_chars
    )
    estimated_prompt_chars = estimate_prompt_budget_contribution(form)
    if estimated_prompt_chars > budget:
        issues.append(
            ValidationIssue(
                path="prompt_budget",
                code="PROMPT_BUDGET_EXCEEDED",
                message=(
                    f"Estimated prompt character contribution "
                    f"{estimated_prompt_chars} exceeds prompt budget {budget}"
                ),
            )
        )

    has_errors = any(i.severity == "error" for i in issues)
    return ValidationReport(
        is_valid=not has_errors,
        issues=tuple(issues),
        estimated_prompt_chars=estimated_prompt_chars,
        criteria_count=total_criteria,
    )


__all__ = [
    "AGENT_MANIFEST_REGISTRY_V1",
    "AGENT_MANIFEST_VERSION_REGISTRY",
    "COORDINATOR_MANIFEST_V1",
    "COORDINATOR_MANIFEST_V2",
    "GAD_MANIFEST_V1",
    "ITSO_MANIFEST_V1",
    "SME_MANIFEST_V1",
    "AgentCapabilityManifest",
    "StrategyCapability",
    "estimate_prompt_budget_contribution",
    "get_agent_manifest",
    "resolve_criterion_measurement_shape",
    "resolve_measurement_shape",
    "validate_form",
]
