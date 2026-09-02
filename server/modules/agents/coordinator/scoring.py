"""Scoring and measurement transformation for Coordinator criteria.

Copy-adapted from ``server/modules/agents/sme/scoring.py``. Task 8 lands this as a
bare copy (no ``sme`` import); Task 9 adds ``score_curriculum_alignment`` plus its
dispatch branch.
"""

from __future__ import annotations

from typing import Any

from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    GroundedInstance,
    GroundedInstanceMeasurement,
    GroundedScoreMeasurement,
    GroundedUnit,
    LlmRubricGuidanceConfig,
    QualifyingUnitsMeasurement,
    RatioBandConfig,
)
from server.modules.rubrics.strategies.calculators import (
    normalize_llm_guidance_score,
    score_count,
    score_ratio,
)

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError


def score_criterion_measurement(
    criterion: CriterionDefinition,
    measurement_dict: dict[str, Any],
) -> CriterionScore:
    """Deterministically score a validated measurement dict using pure calculators."""
    config = criterion.strategy_config

    if isinstance(config, LlmRubricGuidanceConfig):
        measurement = GroundedScoreMeasurement(
            score=measurement_dict["score"],
            evidence=measurement_dict["evidence"],
            reasoning=measurement_dict.get("reasoning"),
        )
        norm_res = normalize_llm_guidance_score(config, measurement)
        score = norm_res.score
        justification = (
            measurement.reasoning
            if measurement.reasoning and measurement.reasoning.strip()
            else (
                f"Evaluated under {criterion.title} guidance "
                f"(score {norm_res.score}/4)."
            )
        )
        evidence = (measurement.evidence,)

    elif isinstance(config, CountBandConfig):
        raw_instances = measurement_dict.get("instances", [])
        instances = tuple(
            GroundedInstance(
                excerpt=inst["excerpt"],
                explanation=inst.get("explanation"),
                location=inst.get("location"),
            )
            for inst in raw_instances
        )
        measurement_inst = GroundedInstanceMeasurement(
            instances=instances,
            summary=measurement_dict.get("summary"),
        )
        count_res = score_count(config, measurement_inst)
        score = count_res.score
        thresholds_str = (
            f"thresholds: 4>={config.threshold_4}, "
            f"3>={config.threshold_3}, "
            f"2>={config.threshold_2}"
        )
        justification = (
            f"Grounded count evaluation: {count_res.count} instance(s) found "
            f"({thresholds_str}). Score {count_res.score}."
        )
        evidence = tuple(inst.excerpt for inst in instances[:8])

    elif isinstance(config, RatioBandConfig):
        raw_units = measurement_dict.get("total_units", [])
        units = tuple(
            GroundedUnit(
                unit_id=u["unit_id"],
                evidence=u["evidence"],
                label=u.get("label"),
                location=u.get("location"),
            )
            for u in raw_units
        )
        qualifying_ids = tuple(measurement_dict.get("qualifying_unit_ids", []))
        has_measurable = measurement_dict.get("has_measurable_content", True)
        measurement_ratio = QualifyingUnitsMeasurement(
            total_units=units,
            qualifying_unit_ids=qualifying_ids,
            has_measurable_content=has_measurable,
            summary=measurement_dict.get("summary"),
        )
        ratio_res = score_ratio(config, measurement_ratio)
        score = ratio_res.score

        if ratio_res.short_sample_applied:
            issues = (
                int(ratio_res.metric_value) if ratio_res.metric_value is not None else 0
            )
            justification = (
                "Coverage ratio evaluation (short sample applied): "
                f"{ratio_res.qualifying_count}/{ratio_res.total_count} "
                f"qualifying unit(s) with {issues} issue(s). "
                f"Score {ratio_res.score}."
            )
        elif not has_measurable or ratio_res.total_count == 0:
            justification = (
                "Coverage ratio evaluation: no measurable content found. "
                f"Score {ratio_res.score}."
            )
        else:
            pct = ratio_res.metric_value if ratio_res.metric_value is not None else 0.0
            justification = (
                f"Coverage ratio evaluation: {ratio_res.qualifying_count}/"
                f"{ratio_res.total_count} qualifying unit(s) "
                f"({pct:.1f}% coverage). Score {ratio_res.score}."
            )

        qual_excerpts = [u.evidence for u in units if u.unit_id in qualifying_ids]
        non_qual_excerpts = [
            u.evidence for u in units if u.unit_id not in qualifying_ids
        ]
        evidence = tuple((qual_excerpts + non_qual_excerpts)[:8])

    else:
        raise AgentExecutionError(
            f"Unsupported strategy config type: {type(config).__name__}"
        )

    return CriterionScore(
        criterion_id=criterion.criterion_code,
        criterion_title=criterion.title,
        score=score,
        justification=justification,
        chunk_ids=(),
        evidence=evidence,
    )


def score_envelope(
    criteria: tuple[CriterionDefinition, ...],
    parsed_response: dict[str, Any],
) -> tuple[CriterionScore, ...]:
    """Score all criteria in an envelope from validated measurements."""
    measurements = parsed_response["criterion_measurements"]
    return tuple(
        score_criterion_measurement(crit, m)
        for crit, m in zip(criteria, measurements, strict=True)
    )


__all__ = ["score_criterion_measurement", "score_envelope"]
