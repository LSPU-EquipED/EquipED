"""Pure DB-free strategy calculators for dynamic CID evaluation forms."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..contracts import (
    CountBandConfig,
    FrozenContractModel,
    GroundedInstanceMeasurement,
    GroundedScoreMeasurement,
    LlmRubricGuidanceConfig,
    PairedCountsMeasurement,
    QualifyingUnitsMeasurement,
    RatioBandConfig,
)


class CountScoreResult(FrozenContractModel):
    """Deterministic count scoring result."""

    score: int = Field(..., ge=1, le=4)
    count: int = Field(..., ge=0)
    mode: Literal["minimum_count", "maximum_count"]


class RatioScoreResult(FrozenContractModel):
    """Deterministic ratio scoring result."""

    score: int = Field(..., ge=1, le=4)
    mode: Literal["coverage_percentage", "absolute_difference"]
    metric_value: float | None = None
    total_count: int | None = None
    qualifying_count: int | None = None
    difference: int | None = None
    short_sample_applied: bool = False


class GuidanceScoreResult(FrozenContractModel):
    """Deterministic LLM guidance score normalization result."""

    score: int = Field(..., ge=1, le=4)


def score_count(
    config: CountBandConfig,
    measurement: GroundedInstanceMeasurement,
) -> CountScoreResult:
    """Deterministically score a grounded count measurement against a CountBandConfig.

    Modes:
    - minimum_count: count >= threshold_4 -> 4, >= threshold_3 -> 3,
      >= threshold_2 -> 2, else 1.
    - maximum_count: count <= threshold_4 -> 4, <= threshold_3 -> 3,
      <= threshold_2 -> 2, else 1.
    """
    if not isinstance(config, CountBandConfig):
        raise TypeError(f"Expected CountBandConfig, got {type(config).__name__}")

    if not isinstance(measurement, GroundedInstanceMeasurement):
        raise TypeError(
            f"Expected GroundedInstanceMeasurement, got {type(measurement).__name__}"
        )

    count = len(measurement.instances)

    if config.mode == "minimum_count":
        if count >= config.threshold_4:
            score = 4
        elif count >= config.threshold_3:
            score = 3
        elif count >= config.threshold_2:
            score = 2
        else:
            score = 1
    elif config.mode == "maximum_count":
        if count <= config.threshold_4:
            score = 4
        elif count <= config.threshold_3:
            score = 3
        elif count <= config.threshold_2:
            score = 2
        else:
            score = 1
    else:
        raise ValueError(f"Unsupported count mode: {config.mode}")

    return CountScoreResult(score=score, count=count, mode=config.mode)


def score_ratio(
    config: RatioBandConfig,
    measurement: QualifyingUnitsMeasurement | PairedCountsMeasurement,
) -> RatioScoreResult:
    """Deterministically score a ratio measurement against a RatioBandConfig.

    Modes:
    - coverage_percentage: Requires QualifyingUnitsMeasurement.
      If has_measurable_content is False, returns score 1 with metric_value=None.
      Calculates (qualifying / total) * 100. If short_sample is configured
      and total < short_sample.min_units, scores by allowable issue count
      (issues = total - qualifying). An empty denominator without short_sample
      scores 1 with metric_value=None.
    - absolute_difference: Requires PairedCountsMeasurement.
      Calculates abs(count_a - count_b). Smaller difference scores higher.
    """
    if not isinstance(config, RatioBandConfig):
        raise TypeError(f"Expected RatioBandConfig, got {type(config).__name__}")

    if config.mode == "coverage_percentage":
        if not isinstance(measurement, QualifyingUnitsMeasurement):
            raise TypeError(
                f"Mode mismatch: config mode '{config.mode}' requires "
                f"QualifyingUnitsMeasurement, got {type(measurement).__name__}"
            )

        if not measurement.has_measurable_content:
            return RatioScoreResult(
                score=1,
                mode=config.mode,
                metric_value=None,
                total_count=0,
                qualifying_count=0,
                difference=None,
                short_sample_applied=False,
            )

        total = measurement.total_count
        qualifying = measurement.qualifying_count

        if config.short_sample is not None and total < config.short_sample.min_units:
            issues = total - qualifying
            if issues <= config.short_sample.max_issues_4:
                score = 4
            elif issues <= config.short_sample.max_issues_3:
                score = 3
            elif issues <= config.short_sample.max_issues_2:
                score = 2
            else:
                score = 1

            return RatioScoreResult(
                score=score,
                mode=config.mode,
                metric_value=float(issues),
                total_count=total,
                qualifying_count=qualifying,
                difference=None,
                short_sample_applied=True,
            )

        if total == 0:
            return RatioScoreResult(
                score=1,
                mode=config.mode,
                metric_value=None,
                total_count=0,
                qualifying_count=0,
                difference=None,
                short_sample_applied=False,
            )

        pct = (qualifying / total) * 100.0
        if pct >= config.threshold_4:
            score = 4
        elif pct >= config.threshold_3:
            score = 3
        elif pct >= config.threshold_2:
            score = 2
        else:
            score = 1

        return RatioScoreResult(
            score=score,
            mode=config.mode,
            metric_value=pct,
            total_count=total,
            qualifying_count=qualifying,
            difference=None,
            short_sample_applied=False,
        )

    if config.mode == "absolute_difference":
        if not isinstance(measurement, PairedCountsMeasurement):
            raise TypeError(
                f"Mode mismatch: config mode '{config.mode}' requires "
                f"PairedCountsMeasurement, got {type(measurement).__name__}"
            )

        diff = abs(measurement.count_a - measurement.count_b)
        if diff <= config.threshold_4:
            score = 4
        elif diff <= config.threshold_3:
            score = 3
        elif diff <= config.threshold_2:
            score = 2
        else:
            score = 1

        return RatioScoreResult(
            score=score,
            mode=config.mode,
            metric_value=float(diff),
            total_count=measurement.count_a + measurement.count_b,
            qualifying_count=None,
            difference=diff,
            short_sample_applied=False,
        )

    raise ValueError(f"Unsupported ratio mode: {config.mode}")


def normalize_llm_guidance_score(
    config: LlmRubricGuidanceConfig,
    measurement: GroundedScoreMeasurement,
) -> GuidanceScoreResult:
    """Normalize and validate a grounded LLM score measurement to 1..4."""
    if not isinstance(config, LlmRubricGuidanceConfig):
        raise TypeError(
            f"Expected LlmRubricGuidanceConfig, got {type(config).__name__}"
        )

    if not isinstance(measurement, GroundedScoreMeasurement):
        raise TypeError(
            f"Expected GroundedScoreMeasurement, got {type(measurement).__name__}"
        )

    return GuidanceScoreResult(score=measurement.score)


__all__ = [
    "CountScoreResult",
    "GuidanceScoreResult",
    "RatioScoreResult",
    "normalize_llm_guidance_score",
    "score_count",
    "score_ratio",
]
