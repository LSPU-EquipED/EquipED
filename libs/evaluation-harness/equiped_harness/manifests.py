"""Pure capability manifests and validation logic for evaluation forms."""

from __future__ import annotations

import json
from types import MappingProxyType
from typing import Any

from equiped_harness.agents.coordinator.capabilities import (
    COORDINATOR_MANIFEST_V1,
    COORDINATOR_MANIFEST_V2,
    COORDINATOR_MANIFEST_V3,
    COORDINATOR_MANIFEST_V4,
)
from equiped_harness.agents.gad.capabilities import GAD_MANIFEST_V1, GAD_MANIFEST_V2
from equiped_harness.agents.itso.capabilities import (
    ITSO_MANIFEST_V1,
    ITSO_MANIFEST_V2,
    ITSO_MANIFEST_V3,
)
from equiped_harness.agents.sme.capabilities import SME_MANIFEST_V1
from equiped_harness.contracts import (
    MAX_FORM_JSON_BYTES,
    CountBandConfig,
    CriterionDefinition,
    FormDefinition,
    RatioBandConfig,
    ValidationIssue,
    ValidationReport,
    calculate_form_json_bytes,
)
from equiped_harness.contracts.capabilities import (
    AgentCapabilityManifest,
    StrategyCapability,
)

# ---------------------------------------------------------------------------
# Exact Manifest Constants (V1)
# ---------------------------------------------------------------------------

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
        ("gad", 2): GAD_MANIFEST_V2,
        ("itso", 1): ITSO_MANIFEST_V1,
        ("itso", 2): ITSO_MANIFEST_V2,
        ("itso", 3): ITSO_MANIFEST_V3,
        ("coordinator", 1): COORDINATOR_MANIFEST_V1,
        ("coordinator", 2): COORDINATOR_MANIFEST_V2,
        ("coordinator", 3): COORDINATOR_MANIFEST_V3,
        ("coordinator", 4): COORDINATOR_MANIFEST_V4,
    }
)


def uses_managed_prompt(agent_id: str, adapter_version: int | None = None) -> bool:
    """Whether this built-in specialist adapter consumes a managed prompt."""
    del adapter_version
    if agent_id not in {"sme", "coordinator", "gad", "itso"}:
        raise ValueError(f"Unknown agent capability manifest for '{agent_id}'")
    return agent_id in {"sme", "gad"}


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

            if strategy == "objective_gauging" and criterion.criterion_code != "A-05":
                issues.append(
                    ValidationIssue(
                        path=f"{c_path}.strategy_config.strategy",
                        code="INVALID_OBJECTIVE_GAUGING_CRITERION",
                        message="Objective gauging is reserved for Coordinator A-05",
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
    "COORDINATOR_MANIFEST_V3",
    "GAD_MANIFEST_V1",
    "GAD_MANIFEST_V2",
    "ITSO_MANIFEST_V1",
    "ITSO_MANIFEST_V2",
    "ITSO_MANIFEST_V3",
    "SME_MANIFEST_V1",
    "AgentCapabilityManifest",
    "StrategyCapability",
    "estimate_prompt_budget_contribution",
    "get_agent_manifest",
    "uses_managed_prompt",
    "resolve_criterion_measurement_shape",
    "resolve_measurement_shape",
    "validate_form",
]
