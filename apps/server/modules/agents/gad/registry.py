"""Deterministic scoring for snapshot-configured GAD criteria."""

from __future__ import annotations

import logging
from typing import Any

from server.modules.rubrics.contracts import (
    CountBandConfig,
    GroundedInstance,
    GroundedInstanceMeasurement,
    PairedCountsMeasurement,
    RatioBandConfig,
)
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO
from server.modules.rubrics.strategies.calculators import score_count, score_ratio

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError
from .grounding import MAX_INSTANCES_PER_CRITERION, ground_instances

logger = logging.getLogger(__name__)

REGISTRY_VERSION = 1
"""Deterministic adapter scoring version."""


def score_from_combined(
    combined: dict[str, Any],
    packed_chunks: list[dict[str, Any]],
    form_snapshot: EvaluationFormSnapshotDTO,
) -> tuple[list[CriterionScore], int, int, int]:
    """Adapt combined sections into ``CriterionScore`` values using snapshot configs.

    Returns (scores, evidence_candidates, evidence_accepted, evidence_rejected).
    Each section is passed to pure strategy calculators (score_count/score_ratio)
    with snapshot thresholds.
    """
    if not isinstance(form_snapshot, EvaluationFormSnapshotDTO):
        raise TypeError("form_snapshot must be an EvaluationFormSnapshotDTO instance")

    criteria = [c for d in form_snapshot.form.domains for c in d.criteria]
    scores: list[CriterionScore] = []
    evidence_candidates = 0
    evidence_accepted = 0
    evidence_rejected = 0

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
        else:
            raise AgentExecutionError(
                f"Unsupported strategy config for criterion {crit.criterion_code}"
            )

    return scores, evidence_candidates, evidence_accepted, evidence_rejected


__all__ = [
    "REGISTRY_VERSION",
    "score_from_combined",
]
