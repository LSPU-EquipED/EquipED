"""Pure DB-free domain and strategy contracts for dynamic CID evaluation forms."""

from __future__ import annotations

import json
import math
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Size and Bound Constants
# ---------------------------------------------------------------------------

MAX_CODE_LENGTH: int = 50
MAX_TITLE_LENGTH: int = 200
MAX_DESCRIPTION_LENGTH: int = 4000
MAX_SCORING_RULE_LENGTH: int = 4000
MAX_GUIDANCE_LENGTH: int = 4000
MAX_DESCRIPTOR_LENGTH: int = 2000
MAX_LOCATION_LENGTH: int = 200
MAX_LABEL_LENGTH: int = 200

MAX_DOMAINS_PER_FORM: int = 20
MAX_CRITERIA_PER_DOMAIN: int = 50
MAX_CRITERIA_PER_FORM: int = 100
MAX_LEVEL_DESCRIPTORS: int = 4
MAX_INSTANCES_PER_MEASUREMENT: int = 100
MAX_UNITS_PER_MEASUREMENT: int = 200
MAX_ALIGNMENTS_PER_MEASUREMENT: int = 100

MAX_COUNT_THRESHOLD: int = 100_000
MAX_DIFFERENCE_THRESHOLD: float = 100_000.0

MAX_CONFIG_JSON_BYTES: int = 16 * 1024  # 16 KB
MAX_FORM_JSON_BYTES: int = 256 * 1024  # 256 KB


def _validate_finite_number(value: float, field_name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be a finite number")
    return value


def _clean_non_empty_str(value: str, field_name: str, max_length: int) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty or blank")
    if len(stripped) > max_length:
        raise ValueError(
            f"{field_name} length {len(stripped)} exceeds max length {max_length}"
        )
    return stripped


def _clean_optional_str(
    value: str | None, field_name: str, max_length: int
) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank when provided")
    if len(stripped) > max_length:
        raise ValueError(
            f"{field_name} length {len(stripped)} exceeds max length {max_length}"
        )
    return stripped


# ---------------------------------------------------------------------------
# Base Contract Models
# ---------------------------------------------------------------------------


class FrozenContractModel(BaseModel):
    """Immutable, strict Pydantic model prohibiting extra fields."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=False,
        allow_inf_nan=False,
    )


class FrozenStrategyConfig(FrozenContractModel):
    """Base strategy configuration with size limits and unknown-field forbidding."""

    @model_validator(mode="after")
    def _validate_config_json_size(self) -> FrozenStrategyConfig:
        config_bytes = calculate_config_json_bytes(self)
        if config_bytes > MAX_CONFIG_JSON_BYTES:
            raise ValueError(
                f"Serialized strategy config size {config_bytes} bytes "
                f"exceeds maximum allowed {MAX_CONFIG_JSON_BYTES} bytes"
            )
        return self


# ---------------------------------------------------------------------------
# Strategy Configuration Models (Discriminated Union)
# ---------------------------------------------------------------------------


class LlmScoreDescriptor(FrozenContractModel):
    """Descriptor for an exact institutional score (1..4)."""

    score: int = Field(..., ge=1, le=4)
    descriptor: str = Field(..., min_length=1, max_length=MAX_DESCRIPTOR_LENGTH)

    @field_validator("descriptor")
    @classmethod
    def _validate_descriptor(cls, value: str) -> str:
        return _clean_non_empty_str(value, "descriptor", MAX_DESCRIPTOR_LENGTH)


class LlmRubricGuidanceConfig(FrozenStrategyConfig):
    """Strategy config for LLM-evaluated criteria with optional level descriptors."""

    strategy: Literal["llm_rubric_guidance"] = "llm_rubric_guidance"
    guidance: str = Field(..., min_length=1, max_length=MAX_GUIDANCE_LENGTH)
    level_descriptors: tuple[LlmScoreDescriptor, ...] | None = None

    @field_validator("guidance")
    @classmethod
    def _validate_guidance(cls, value: str) -> str:
        return _clean_non_empty_str(value, "guidance", MAX_GUIDANCE_LENGTH)

    @field_validator("level_descriptors", mode="before")
    @classmethod
    def _convert_level_descriptors(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def _validate_descriptors(self) -> LlmRubricGuidanceConfig:
        if self.level_descriptors is not None:
            if len(self.level_descriptors) != 4:
                raise ValueError(
                    "level_descriptors must provide exactly 4 entries "
                    "covering scores 1..4"
                )
            scores = {desc.score for desc in self.level_descriptors}
            if scores != {1, 2, 3, 4}:
                raise ValueError(
                    "level_descriptors must cover exact scores 1..4 "
                    f"without duplicates, got {scores}"
                )
        return self


class CountBandConfig(FrozenStrategyConfig):
    """Deterministic count thresholds covering scores 4/3/2/1.

    Modes:
    - minimum_count: count >= threshold_4 -> 4, >= threshold_3 -> 3,
      >= threshold_2 -> 2, else 1. Thresholds are strictly descending
      positive integers: threshold_4 > threshold_3 > threshold_2 > 0.
    - maximum_count: count <= threshold_4 -> 4, <= threshold_3 -> 3,
      <= threshold_2 -> 2, else 1. Thresholds are strictly ascending
      nonnegative integers: 0 <= threshold_4 < threshold_3 < threshold_2.
    """

    strategy: Literal["count_band"] = "count_band"
    mode: Literal["minimum_count", "maximum_count"] = "minimum_count"
    threshold_4: int = Field(..., ge=0, le=MAX_COUNT_THRESHOLD)
    threshold_3: int = Field(..., ge=0, le=MAX_COUNT_THRESHOLD)
    threshold_2: int = Field(..., ge=0, le=MAX_COUNT_THRESHOLD)

    @model_validator(mode="after")
    def _validate_threshold_ordering(self) -> CountBandConfig:
        if self.mode == "minimum_count":
            if not (self.threshold_4 > self.threshold_3 > self.threshold_2 > 0):
                raise ValueError(
                    "Count minimum_count thresholds must be strictly descending "
                    f"positive integers: threshold_4 ({self.threshold_4}) > "
                    f"threshold_3 ({self.threshold_3}) > threshold_2 "
                    f"({self.threshold_2}) > 0"
                )
        elif self.mode == "maximum_count":
            if not (
                0
                <= self.threshold_4
                < self.threshold_3
                < self.threshold_2
                <= MAX_COUNT_THRESHOLD
            ):
                raise ValueError(
                    "Count maximum_count thresholds must be strictly ascending "
                    f"non-negative integers: 0 <= threshold_4 ({self.threshold_4}) < "
                    f"threshold_3 ({self.threshold_3}) < threshold_2 "
                    f"({self.threshold_2})"
                )
        return self


class ShortSampleConfig(FrozenContractModel):
    """Short-sample issue-count override for small unit counts (e.g. OP-01).

    If total units < min_units, score by maximum allowable issues:
    issues <= max_issues_4 -> 4, <= max_issues_3 -> 3,
    issues <= max_issues_2 -> 2, else 1.
    """

    min_units: int = Field(..., ge=1, le=MAX_COUNT_THRESHOLD)
    max_issues_4: int = Field(..., ge=0, le=MAX_COUNT_THRESHOLD)
    max_issues_3: int = Field(..., ge=0, le=MAX_COUNT_THRESHOLD)
    max_issues_2: int = Field(..., ge=0, le=MAX_COUNT_THRESHOLD)

    @model_validator(mode="after")
    def _validate_monotonic_issues(self) -> ShortSampleConfig:
        if not (0 <= self.max_issues_4 < self.max_issues_3 < self.max_issues_2):
            raise ValueError(
                "Short sample max issues must be strictly monotonic ascending: "
                f"0 <= max_issues_4 ({self.max_issues_4}) < max_issues_3 "
                f"({self.max_issues_3}) < max_issues_2 ({self.max_issues_2})"
            )
        return self


class RatioBandConfig(FrozenStrategyConfig):
    """Deterministic ratio band configuration."""

    strategy: Literal["ratio_band"] = "ratio_band"
    mode: Literal["coverage_percentage", "absolute_difference"] = "coverage_percentage"
    threshold_4: float
    threshold_3: float
    threshold_2: float
    short_sample: ShortSampleConfig | None = None

    @model_validator(mode="after")
    def _validate_thresholds(self) -> RatioBandConfig:
        _validate_finite_number(self.threshold_4, "threshold_4")
        _validate_finite_number(self.threshold_3, "threshold_3")
        _validate_finite_number(self.threshold_2, "threshold_2")

        if self.mode == "coverage_percentage":
            if not (
                100.0 >= self.threshold_4 > self.threshold_3 > self.threshold_2 > 0.0
            ):
                raise ValueError(
                    "Coverage percentage thresholds must be strictly monotonic "
                    f"descending within (0, 100]: 100.0 >= threshold_4 "
                    f"({self.threshold_4}) > threshold_3 ({self.threshold_3}) > "
                    f"threshold_2 ({self.threshold_2}) > 0.0"
                )
        elif self.mode == "absolute_difference":
            if self.short_sample is not None:
                raise ValueError(
                    "short_sample override is not permitted for "
                    "absolute_difference mode"
                )
            if not (
                0.0
                <= self.threshold_4
                < self.threshold_3
                < self.threshold_2
                <= MAX_DIFFERENCE_THRESHOLD
            ):
                raise ValueError(
                    "Absolute difference thresholds must be strictly monotonic "
                    f"ascending non-negative within [0, {MAX_DIFFERENCE_THRESHOLD}]: "
                    f"0.0 <= threshold_4 ({self.threshold_4}) < threshold_3 "
                    f"({self.threshold_3}) < threshold_2 ({self.threshold_2})"
                )
        return self


class CurriculumAlignmentConfig(FrozenStrategyConfig):
    """Coordinator-only curriculum objective alignment scoring configuration."""

    strategy: Literal["curriculum_alignment"] = "curriculum_alignment"
    guidance: str | None = Field(None, max_length=MAX_GUIDANCE_LENGTH)

    @field_validator("guidance")
    @classmethod
    def _validate_guidance(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "guidance", MAX_GUIDANCE_LENGTH)


StrategyConfig = Annotated[
    LlmRubricGuidanceConfig
    | CountBandConfig
    | RatioBandConfig
    | CurriculumAlignmentConfig,
    Field(discriminator="strategy"),
]


# ---------------------------------------------------------------------------
# Measurement DTOs (Shape Contracts Only)
# ---------------------------------------------------------------------------


class GroundedScoreMeasurement(FrozenContractModel):
    """Measurement shape for LLM score and evidence."""

    score: int = Field(..., ge=1, le=4)
    evidence: str = Field(..., min_length=1, max_length=MAX_DESCRIPTION_LENGTH)
    reasoning: str | None = Field(None, max_length=MAX_DESCRIPTION_LENGTH)

    @field_validator("evidence")
    @classmethod
    def _validate_evidence(cls, value: str) -> str:
        return _clean_non_empty_str(value, "evidence", MAX_DESCRIPTION_LENGTH)

    @field_validator("reasoning")
    @classmethod
    def _validate_reasoning(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "reasoning", MAX_DESCRIPTION_LENGTH)


class GroundedInstance(FrozenContractModel):
    """Single grounded instance excerpt with optional explanation and location."""

    excerpt: str = Field(..., min_length=1, max_length=MAX_DESCRIPTION_LENGTH)
    explanation: str | None = Field(None, max_length=MAX_DESCRIPTION_LENGTH)
    location: str | None = Field(None, max_length=MAX_LOCATION_LENGTH)

    @field_validator("excerpt")
    @classmethod
    def _validate_excerpt(cls, value: str) -> str:
        return _clean_non_empty_str(value, "excerpt", MAX_DESCRIPTION_LENGTH)

    @field_validator("explanation")
    @classmethod
    def _validate_explanation(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "explanation", MAX_DESCRIPTION_LENGTH)

    @field_validator("location")
    @classmethod
    def _validate_location(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "location", MAX_LOCATION_LENGTH)


class GroundedInstanceMeasurement(FrozenContractModel):
    """Measurement shape for grounded instance lists."""

    instances: tuple[GroundedInstance, ...] = Field(
        ..., max_length=MAX_INSTANCES_PER_MEASUREMENT
    )
    summary: str | None = Field(None, max_length=MAX_DESCRIPTION_LENGTH)

    @field_validator("instances", mode="before")
    @classmethod
    def _convert_instances(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        return value

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "summary", MAX_DESCRIPTION_LENGTH)


class GroundedUnit(FrozenContractModel):
    """Single grounded unit with stable ID and evidence excerpt."""

    unit_id: str = Field(..., min_length=1, max_length=MAX_CODE_LENGTH)
    evidence: str = Field(..., min_length=1, max_length=MAX_DESCRIPTION_LENGTH)
    label: str | None = Field(None, max_length=MAX_LABEL_LENGTH)
    location: str | None = Field(None, max_length=MAX_LOCATION_LENGTH)

    @field_validator("unit_id")
    @classmethod
    def _validate_unit_id(cls, value: str) -> str:
        return _clean_non_empty_str(value, "unit_id", MAX_CODE_LENGTH)

    @field_validator("evidence")
    @classmethod
    def _validate_evidence(cls, value: str) -> str:
        return _clean_non_empty_str(value, "evidence", MAX_DESCRIPTION_LENGTH)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "label", MAX_LABEL_LENGTH)

    @field_validator("location")
    @classmethod
    def _validate_location(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "location", MAX_LOCATION_LENGTH)


class QualifyingUnitsMeasurement(FrozenContractModel):
    """Measurement shape for grounded ratio unit evaluation."""

    total_units: tuple[GroundedUnit, ...] = Field(
        ..., max_length=MAX_UNITS_PER_MEASUREMENT
    )
    qualifying_unit_ids: tuple[str, ...] = Field(
        ..., max_length=MAX_UNITS_PER_MEASUREMENT
    )
    has_measurable_content: bool = True
    summary: str | None = Field(None, max_length=MAX_DESCRIPTION_LENGTH)

    @field_validator("total_units", "qualifying_unit_ids", mode="before")
    @classmethod
    def _convert_to_tuple(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        return value

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "summary", MAX_DESCRIPTION_LENGTH)

    @model_validator(mode="after")
    def _validate_unit_subsets_and_uniqueness(self) -> QualifyingUnitsMeasurement:
        if not self.has_measurable_content and len(self.total_units) > 0:
            raise ValueError(
                "has_measurable_content cannot be False when total_units is not empty"
            )

        seen_total_ids: set[str] = set()
        for u in self.total_units:
            if u.unit_id in seen_total_ids:
                raise ValueError(f"Duplicate unit_id in total_units: '{u.unit_id}'")
            seen_total_ids.add(u.unit_id)

        seen_qual_ids: set[str] = set()
        for q_id in self.qualifying_unit_ids:
            if q_id in seen_qual_ids:
                raise ValueError(f"Duplicate unit_id in qualifying_unit_ids: '{q_id}'")
            if q_id not in seen_total_ids:
                raise ValueError(
                    f"qualifying_unit_id '{q_id}' does not exist in total_units"
                )
            seen_qual_ids.add(q_id)

        return self

    @property
    def qualifying_count(self) -> int:
        return len(self.qualifying_unit_ids)

    @property
    def total_count(self) -> int:
        return len(self.total_units)


class PairedCountsMeasurement(FrozenContractModel):
    """Measurement shape for paired counts (e.g. female/male representations)."""

    count_a: int = Field(..., ge=0, le=MAX_COUNT_THRESHOLD)
    count_b: int = Field(..., ge=0, le=MAX_COUNT_THRESHOLD)
    summary: str | None = Field(None, max_length=MAX_DESCRIPTION_LENGTH)

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "summary", MAX_DESCRIPTION_LENGTH)


class ObjectiveAlignmentRow(FrozenContractModel):
    """Single curriculum objective alignment row."""

    objective_text: str = Field(..., min_length=1, max_length=MAX_DESCRIPTION_LENGTH)
    is_aligned: bool
    objective_id: str | None = Field(None, max_length=MAX_CODE_LENGTH)
    assessment_excerpt: str | None = Field(None, max_length=MAX_DESCRIPTION_LENGTH)
    reasoning: str | None = Field(None, max_length=MAX_DESCRIPTION_LENGTH)

    @field_validator("objective_text")
    @classmethod
    def _validate_objective_text(cls, value: str) -> str:
        return _clean_non_empty_str(value, "objective_text", MAX_DESCRIPTION_LENGTH)

    @field_validator("objective_id")
    @classmethod
    def _validate_objective_id(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "objective_id", MAX_CODE_LENGTH)

    @field_validator("assessment_excerpt")
    @classmethod
    def _validate_assessment_excerpt(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "assessment_excerpt", MAX_DESCRIPTION_LENGTH)

    @field_validator("reasoning")
    @classmethod
    def _validate_reasoning(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "reasoning", MAX_DESCRIPTION_LENGTH)


class CurriculumAlignmentMeasurement(FrozenContractModel):
    """Measurement shape for Coordinator curriculum objective alignments."""

    alignments: tuple[ObjectiveAlignmentRow, ...] = Field(
        ..., max_length=MAX_ALIGNMENTS_PER_MEASUREMENT
    )
    summary: str | None = Field(None, max_length=MAX_DESCRIPTION_LENGTH)

    @field_validator("alignments", mode="before")
    @classmethod
    def _convert_alignments(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        return value

    @field_validator("summary")
    @classmethod
    def _validate_summary(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "summary", MAX_DESCRIPTION_LENGTH)


# ---------------------------------------------------------------------------
# Definition Models
# ---------------------------------------------------------------------------


class CriterionDefinition(FrozenContractModel):
    """Immutable definition of a single rubric criterion."""

    rubric_criterion_id: uuid.UUID
    criterion_code: str = Field(..., min_length=1, max_length=MAX_CODE_LENGTH)
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LENGTH)
    description: str = Field(..., min_length=1, max_length=MAX_DESCRIPTION_LENGTH)
    scoring_rule: str | None = Field(None, max_length=MAX_SCORING_RULE_LENGTH)
    display_order: int = Field(..., ge=0)
    strategy_config: StrategyConfig

    @field_validator("criterion_code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        return _clean_non_empty_str(value, "criterion_code", MAX_CODE_LENGTH)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _clean_non_empty_str(value, "title", MAX_TITLE_LENGTH)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        return _clean_non_empty_str(value, "description", MAX_DESCRIPTION_LENGTH)

    @field_validator("scoring_rule")
    @classmethod
    def _validate_scoring_rule(cls, value: str | None) -> str | None:
        return _clean_optional_str(value, "scoring_rule", MAX_SCORING_RULE_LENGTH)


class DomainDefinition(FrozenContractModel):
    """Immutable definition of a rubric domain containing criteria."""

    rubric_domain_id: uuid.UUID
    code: str = Field(..., min_length=1, max_length=MAX_CODE_LENGTH)
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LENGTH)
    display_order: int = Field(..., ge=0)
    criteria: tuple[CriterionDefinition, ...] = Field(
        ..., min_length=1, max_length=MAX_CRITERIA_PER_DOMAIN
    )

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        return _clean_non_empty_str(value, "code", MAX_CODE_LENGTH)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _clean_non_empty_str(value, "title", MAX_TITLE_LENGTH)

    @field_validator("criteria", mode="before")
    @classmethod
    def _convert_criteria(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        return value


class FormDefinition(FrozenContractModel):
    """Immutable definition of an evaluation form revision."""

    rubric_set_id: uuid.UUID
    agent_id: str = Field(..., min_length=1, max_length=MAX_CODE_LENGTH)
    name: str = Field(..., min_length=1, max_length=MAX_TITLE_LENGTH)
    version_number: int = Field(..., ge=1)
    adapter_key: str = Field(..., min_length=1, max_length=MAX_CODE_LENGTH)
    adapter_version: int = Field(..., ge=1)
    domains: tuple[DomainDefinition, ...] = Field(
        ..., min_length=1, max_length=MAX_DOMAINS_PER_FORM
    )

    @field_validator("agent_id")
    @classmethod
    def _validate_agent_id(cls, value: str) -> str:
        return _clean_non_empty_str(value, "agent_id", MAX_CODE_LENGTH)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _clean_non_empty_str(value, "name", MAX_TITLE_LENGTH)

    @field_validator("adapter_key")
    @classmethod
    def _validate_adapter_key(cls, value: str) -> str:
        return _clean_non_empty_str(value, "adapter_key", MAX_CODE_LENGTH)

    @field_validator("domains", mode="before")
    @classmethod
    def _convert_domains(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def _validate_total_criteria_and_size(self) -> FormDefinition:
        total_criteria = sum(len(d.criteria) for d in self.domains)
        if total_criteria > MAX_CRITERIA_PER_FORM:
            raise ValueError(
                f"Total criteria count {total_criteria} exceeds max limit "
                f"{MAX_CRITERIA_PER_FORM}"
            )
        json_bytes = calculate_form_json_bytes(self)
        if json_bytes > MAX_FORM_JSON_BYTES:
            raise ValueError(
                f"Serialized form size {json_bytes} bytes exceeds max limit "
                f"{MAX_FORM_JSON_BYTES} bytes"
            )
        return self


# ---------------------------------------------------------------------------
# Validation Report and Issues
# ---------------------------------------------------------------------------

ValidationSeverity = Literal["error", "warning", "info"]


class ValidationIssue(FrozenContractModel):
    """Structured issue produced by form or manifest validation."""

    path: str
    code: str
    message: str
    severity: ValidationSeverity = "error"


class ValidationReport(FrozenContractModel):
    """Validation report aggregating issues, criteria count, and budget."""

    is_valid: bool
    issues: tuple[ValidationIssue, ...] = ()
    estimated_prompt_chars: int = 0
    criteria_count: int = 0

    @field_validator("issues", mode="before")
    @classmethod
    def _convert_issues(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return tuple(value)
        return value

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")


# ---------------------------------------------------------------------------
# Canonical Ordering and Serialization Helpers
# ---------------------------------------------------------------------------


def calculate_form_json_bytes(form: FormDefinition) -> int:
    """Calculate deterministic UTF-8 JSON size in bytes for a FormDefinition."""
    payload = form.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return len(serialized)


def calculate_config_json_bytes(
    config: StrategyConfig | FrozenStrategyConfig,
) -> int:
    """Calculate deterministic UTF-8 JSON size in bytes for a StrategyConfig."""
    payload = config.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return len(serialized)


def canonicalize_form(form: FormDefinition) -> FormDefinition:
    """Return a new FormDefinition with domains and criteria canonically ordered.

    Ordering:
    - Domains sorted by display_order, then code.
    - Criteria within each domain sorted by display_order, then criterion_code.
    """
    sorted_domains: list[DomainDefinition] = []
    for domain in sorted(form.domains, key=lambda d: (d.display_order, d.code)):
        sorted_criteria = tuple(
            sorted(
                domain.criteria,
                key=lambda c: (c.display_order, c.criterion_code),
            )
        )
        sorted_domains.append(
            DomainDefinition(
                rubric_domain_id=domain.rubric_domain_id,
                code=domain.code,
                title=domain.title,
                display_order=domain.display_order,
                criteria=sorted_criteria,
            )
        )

    return FormDefinition(
        rubric_set_id=form.rubric_set_id,
        agent_id=form.agent_id,
        name=form.name,
        version_number=form.version_number,
        adapter_key=form.adapter_key,
        adapter_version=form.adapter_version,
        domains=tuple(sorted_domains),
    )


__all__ = [
    "MAX_ALIGNMENTS_PER_MEASUREMENT",
    "MAX_CODE_LENGTH",
    "MAX_CONFIG_JSON_BYTES",
    "MAX_COUNT_THRESHOLD",
    "MAX_CRITERIA_PER_DOMAIN",
    "MAX_CRITERIA_PER_FORM",
    "MAX_DESCRIPTION_LENGTH",
    "MAX_DESCRIPTOR_LENGTH",
    "MAX_DIFFERENCE_THRESHOLD",
    "MAX_DOMAINS_PER_FORM",
    "MAX_FORM_JSON_BYTES",
    "MAX_GUIDANCE_LENGTH",
    "MAX_INSTANCES_PER_MEASUREMENT",
    "MAX_LABEL_LENGTH",
    "MAX_LEVEL_DESCRIPTORS",
    "MAX_LOCATION_LENGTH",
    "MAX_SCORING_RULE_LENGTH",
    "MAX_TITLE_LENGTH",
    "MAX_UNITS_PER_MEASUREMENT",
    "CountBandConfig",
    "CriterionDefinition",
    "CurriculumAlignmentConfig",
    "CurriculumAlignmentMeasurement",
    "DomainDefinition",
    "FormDefinition",
    "FrozenContractModel",
    "FrozenStrategyConfig",
    "GroundedInstance",
    "GroundedInstanceMeasurement",
    "GroundedScoreMeasurement",
    "GroundedUnit",
    "LlmRubricGuidanceConfig",
    "LlmScoreDescriptor",
    "ObjectiveAlignmentRow",
    "PairedCountsMeasurement",
    "QualifyingUnitsMeasurement",
    "RatioBandConfig",
    "ShortSampleConfig",
    "StrategyConfig",
    "ValidationIssue",
    "ValidationReport",
    "ValidationSeverity",
    "calculate_config_json_bytes",
    "calculate_form_json_bytes",
    "canonicalize_form",
]
