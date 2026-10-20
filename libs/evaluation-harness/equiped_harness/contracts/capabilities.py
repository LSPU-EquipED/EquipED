"""Neutral capability manifest contracts."""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from equiped_harness.contracts import (
    MAX_CODE_LENGTH,
    FrozenContractModel,
    _clean_non_empty_str,
    _clean_optional_str,
)


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


__all__ = ["StrategyCapability", "AgentCapabilityManifest"]
