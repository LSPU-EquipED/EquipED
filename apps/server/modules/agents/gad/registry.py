"""Deterministic scoring for snapshot-configured GAD criteria."""

from __future__ import annotations

import logging
from typing import Any

from server.modules.rubrics.contracts import (
    CountBandConfig,
    GroundedInstance,
    GroundedInstanceMeasurement,
    GroundedScoreMeasurement,
    LlmRubricGuidanceConfig,
    PairedCountsMeasurement,
    RatioBandConfig,
)
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO
from server.modules.rubrics.strategies.calculators import (
    normalize_llm_guidance_score,
    score_count,
    score_ratio,
)

from ..contracts import CriterionScore, UngroundedCriterionAdvisory
from ..exceptions import AgentExecutionError
from .grounding import (
    MAX_INSTANCES_PER_CRITERION,
    ground_instances,
    ground_single_excerpt,
)

logger = logging.getLogger(__name__)

REGISTRY_VERSION = 1
"""Deterministic adapter scoring version."""


def score_from_combined(
    combined: dict[str, Any],
    packed_chunks: list[dict[str, Any]],
    form_snapshot: EvaluationFormSnapshotDTO,
) -> tuple[list[CriterionScore], int, int, int, list[UngroundedCriterionAdvisory]]:
    """Adapt combined sections into ``CriterionScore`` values using snapshot configs.

    Returns (scores, evidence_candidates, evidence_accepted, evidence_rejected,
    ungrounded_advisories). Each section is passed to pure strategy calculators
    (score_count/score_ratio) with snapshot thresholds.
    """
    if not isinstance(form_snapshot, EvaluationFormSnapshotDTO):
        raise TypeError("form_snapshot must be an EvaluationFormSnapshotDTO instance")

    criteria = [c for d in form_snapshot.form.domains for c in d.criteria]
    scores: list[CriterionScore] = []
    evidence_candidates = 0
    evidence_accepted = 0
    evidence_rejected = 0
    ungrounded_advisories: list[UngroundedCriterionAdvisory] = []

    for crit in criteria:
        section_key = crit.criterion_code.strip().casefold()
        section = combined.get(section_key)
        if section is None or not isinstance(section, dict):
            raise AgentExecutionError(
                f"Missing or invalid section for {crit.criterion_code}: "
                f"section must be present and a dict after parsing"
            )

        config = crit.strategy_config
        if isinstance(config, RatioBandConfig):
            female_count = int(section.get("female_count", 0))
            male_count = int(section.get("male_count", 0))
            summary = str(section.get("summary", "")).strip()

            measurement = PairedCountsMeasurement(
                count_a=female_count,
                count_b=male_count,
                summary=summary or None,
            )
            score_res = score_ratio(config, measurement)
            diff = (
                score_res.difference
                if score_res.difference is not None
                else abs(female_count - male_count)
            )
            justification = (
                f"Female representations: {female_count}; male representations: "
                f"{male_count}; absolute difference: {diff}. {summary}"
            )
            scores.append(
                CriterionScore(
                    criterion_id=crit.criterion_code,
                    criterion_title=crit.title,
                    score=score_res.score,
                    justification=justification,
                    chunk_ids=(),
                    evidence=(),
                )
            )
        elif isinstance(config, CountBandConfig):
            raw_instances = section.get("instances", [])
            if not isinstance(raw_instances, list):
                raw_instances = []
            if len(raw_instances) > MAX_INSTANCES_PER_CRITERION:
                raw_instances = raw_instances[:MAX_INSTANCES_PER_CRITERION]
                section["instances"] = raw_instances
                logger.info(
                    "GAD section '%s' truncated to %d instances",
                    crit.criterion_code,
                    MAX_INSTANCES_PER_CRITERION,
                )
            claimed_count = int(section.get("instance_count", 0))
            evidence_candidates += len(raw_instances)

            accepted_excerpts, accepted_ids, rejected = ground_instances(
                section_key, raw_instances, packed_chunks
            )
            evidence_accepted += len(accepted_excerpts)
            evidence_rejected += rejected

            grounded_dtos = tuple(
                GroundedInstance(excerpt=e) for e in accepted_excerpts
            )
            summary = str(section.get("summary", "")).strip()

            measurement = GroundedInstanceMeasurement(
                instances=grounded_dtos,
                summary=summary or None,
            )
            score_res = score_count(config, measurement)

            grounded_count = len(accepted_excerpts)
            justification = (
                f"Grounded unique instances: {grounded_count} "
                f"(model reported {claimed_count}; {rejected} unsupported "
                f"or invalid instance(s) excluded). {summary}"
            )
            scores.append(
                CriterionScore(
                    criterion_id=crit.criterion_code,
                    criterion_title=crit.title,
                    score=score_res.score,
                    justification=justification,
                    chunk_ids=tuple(accepted_ids),
                    evidence=tuple(accepted_excerpts),
                )
            )
        elif isinstance(config, LlmRubricGuidanceConfig):
            raw_score = section.get("score")
            raw_evidence = str(section.get("evidence", "")).strip()
            raw_chunk_id = str(section.get("chunk_id", "")).strip()
            raw_reasoning = section.get("reasoning")
            evidence_candidates += 1

            grounded = ground_single_excerpt(raw_evidence, raw_chunk_id, packed_chunks)
            reasoning = (
                raw_reasoning.strip()
                if isinstance(raw_reasoning, str) and raw_reasoning.strip()
                else None
            )

            if grounded is None:
                evidence_rejected += 1
                ungrounded_advisories.append(
                    UngroundedCriterionAdvisory(
                        criterion_id=crit.criterion_code,
                        reason=(
                            "model evidence could not be grounded in any "
                            "provided document chunk"
                        ),
                    )
                )
                measurement = GroundedScoreMeasurement(
                    score=raw_score,
                    evidence="(evidence could not be grounded)",
                    reasoning=reasoning,
                )
                score_res = normalize_llm_guidance_score(config, measurement)
                justification = reasoning or (
                    f"Evaluated under {crit.title} guidance "
                    f"(score {score_res.score}/4; evidence ungrounded)."
                )
                scores.append(
                    CriterionScore(
                        criterion_id=crit.criterion_code,
                        criterion_title=crit.title,
                        score=score_res.score,
                        justification=justification,
                        chunk_ids=(),
                        evidence=(),
                    )
                )
                continue

            evidence_accepted += 1
            grounded_evidence, grounded_chunk_id = grounded

            measurement = GroundedScoreMeasurement(
                score=raw_score,
                evidence=grounded_evidence,
                reasoning=reasoning,
            )
            score_res = normalize_llm_guidance_score(config, measurement)
            justification = (
                measurement.reasoning
                if measurement.reasoning
                else (
                    f"Evaluated under {crit.title} guidance "
                    f"(score {score_res.score}/4)."
                )
            )
            scores.append(
                CriterionScore(
                    criterion_id=crit.criterion_code,
                    criterion_title=crit.title,
                    score=score_res.score,
                    justification=justification,
                    chunk_ids=(grounded_chunk_id,),
                    evidence=(grounded_evidence,),
                )
            )
        else:
            raise AgentExecutionError(
                f"Unsupported strategy config for criterion {crit.criterion_code}"
            )

    return (
        scores,
        evidence_candidates,
        evidence_accepted,
        evidence_rejected,
        ungrounded_advisories,
    )


__all__ = [
    "REGISTRY_VERSION",
    "score_from_combined",
]
