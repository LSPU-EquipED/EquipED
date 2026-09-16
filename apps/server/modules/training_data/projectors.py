"""Projection functions transforming feedback and agent generations into DPO pairs."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from server.modules.feedback.items import apply_item_rejections
from server.modules.feedback.state import EffectiveCriterionCorrection
from server.modules.synthesis.models import AgentGeneration
from server.modules.training_data.contracts import DpoPair

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    """Result of attempting to project an AgentGeneration into a DpoPair."""

    pair: DpoPair | None = None
    skip_reason: str | None = None
    reviewer_ids: frozenset[uuid.UUID] = frozenset()


def _is_score_shaped(measurement: dict[str, Any]) -> bool:
    """True only for an llm_rubric_guidance measurement."""
    return (
        "score" in measurement
        and "instances" not in measurement
        and "total_units" not in measurement
    )


def project_criterion_measurements_v1(
    generation: AgentGeneration,
    corrections_by_criterion: dict[str, EffectiveCriterionCorrection],
    rejections_by_criterion: dict[str, tuple[frozenset[str], frozenset[uuid.UUID]]],
) -> ProjectionResult:
    """Project generation with contract 'criterion_measurements.v1'.

    Supports:
    1. Score & reasoning edits (for llm_rubric_guidance criteria).
    2. Item rejections (for count_band / ratio_band criteria).

    Rejects or envelopes without real changes are skipped.
    """
    if generation.envelope_status != "ok":
        return ProjectionResult(
            skip_reason=f"envelope_status_{generation.envelope_status}"
        )

    # An envelope with any effective REJECT has no corrected text to construct
    # chosen response from
    if any(corr.action == "REJECT" for corr in corrections_by_criterion.values()):
        return ProjectionResult(skip_reason="envelope_contains_rejection")

    raw_response = generation.response_json
    if not raw_response and generation.response_text:
        try:
            raw_response = json.loads(generation.response_text)
        except Exception:
            raw_response = None

    if not isinstance(raw_response, dict):
        return ProjectionResult(skip_reason="invalid_generation_response_json")

    measurements = raw_response.get("criterion_measurements", [])
    if not isinstance(measurements, list):
        return ProjectionResult(skip_reason="missing_criterion_measurements")

    chosen_measurements: list[dict[str, Any]] = []
    reviewer_ids: set[uuid.UUID] = set()
    real_change = False

    for measurement in measurements:
        if not isinstance(measurement, dict):
            chosen_measurements.append(measurement)
            continue

        cid = measurement.get("criterion_id")
        corr = corrections_by_criterion.get(cid)
        item_rej_entry = rejections_by_criterion.get(cid)

        # Check if item-level rejections apply
        if item_rej_entry and item_rej_entry[0]:
            rej_items, rev_ids = item_rej_entry
            corrected = apply_item_rejections(measurement, rej_items)
            if corrected != measurement:
                real_change = True
                reviewer_ids.update(rev_ids)
                chosen_measurements.append(corrected)
                continue

        # Check if score edit applies
        if corr is not None and corr.action == "EDIT":
            if not _is_score_shaped(measurement):
                return ProjectionResult(
                    skip_reason=f"measurement_not_score_shaped_{cid}"
                )

            new_measurement = dict(measurement)
            if corr.score is not None and corr.score != measurement.get("score"):
                new_measurement["score"] = corr.score
                real_change = True
            if corr.justification:
                trimmed = corr.justification.strip()
                old_reasoning = (measurement.get("reasoning") or "").strip()
                if trimmed and trimmed != old_reasoning:
                    new_measurement["reasoning"] = trimmed
                    real_change = True
            if corr.user_id:
                reviewer_ids.add(corr.user_id)
            chosen_measurements.append(new_measurement)
            continue

        chosen_measurements.append(measurement)

    if not real_change:
        return ProjectionResult(skip_reason="no_real_change")

    chosen_response = {
        **raw_response,
        "criterion_measurements": chosen_measurements,
    }

    pair = DpoPair(
        pair_id=str(generation.generation_id),
        prompt=generation.prompt_text,
        chosen=json.dumps(chosen_response, ensure_ascii=False),
        rejected=generation.response_text,
        generation_id=generation.generation_id,
        evaluation_id=generation.evaluation_id,
        document_id=generation.document_id,
        agent_id=generation.agent_id,
        model_name=generation.model_name,
        reviewer_ids=frozenset(reviewer_ids),
    )
    return ProjectionResult(pair=pair, reviewer_ids=frozenset(reviewer_ids))


def project_itso_scores_v1(
    generation: AgentGeneration,
    corrections_by_criterion: dict[str, EffectiveCriterionCorrection],
) -> ProjectionResult:
    """Project generation with contract 'itso_scores.v1'.

    Supports score and justification edits on ITSO criterion scores.
    """
    if generation.envelope_status != "ok":
        return ProjectionResult(
            skip_reason=f"envelope_status_{generation.envelope_status}"
        )

    if any(corr.action == "REJECT" for corr in corrections_by_criterion.values()):
        return ProjectionResult(skip_reason="envelope_contains_rejection")

    raw_response = generation.response_json
    if not raw_response and generation.response_text:
        try:
            raw_response = json.loads(generation.response_text)
        except Exception:
            raw_response = None

    if not isinstance(raw_response, dict):
        return ProjectionResult(skip_reason="invalid_generation_response_json")

    criterion_scores = raw_response.get("criterion_scores", [])
    if not isinstance(criterion_scores, list):
        return ProjectionResult(skip_reason="missing_criterion_scores")

    chosen_scores: list[dict[str, Any]] = []
    reviewer_ids: set[uuid.UUID] = set()
    real_change = False

    for score_entry in criterion_scores:
        if not isinstance(score_entry, dict):
            chosen_scores.append(score_entry)
            continue

        cid = score_entry.get("criterion_id")
        corr = corrections_by_criterion.get(cid)
        if corr is not None and corr.action == "EDIT":
            new_entry = dict(score_entry)
            if corr.score is not None and corr.score != score_entry.get("score"):
                new_entry["score"] = corr.score
                real_change = True
            if corr.justification:
                trimmed = corr.justification.strip()
                old_just = (score_entry.get("justification") or "").strip()
                if trimmed and trimmed != old_just:
                    new_entry["justification"] = trimmed
                    real_change = True
            if corr.user_id:
                reviewer_ids.add(corr.user_id)
            chosen_scores.append(new_entry)
        else:
            chosen_scores.append(score_entry)

    if not real_change:
        return ProjectionResult(skip_reason="no_real_change")

    chosen_response = {
        **raw_response,
        "criterion_scores": chosen_scores,
    }

    pair = DpoPair(
        pair_id=str(generation.generation_id),
        prompt=generation.prompt_text,
        chosen=json.dumps(chosen_response, ensure_ascii=False),
        rejected=generation.response_text,
        generation_id=generation.generation_id,
        evaluation_id=generation.evaluation_id,
        document_id=generation.document_id,
        agent_id=generation.agent_id,
        model_name=generation.model_name,
        reviewer_ids=frozenset(reviewer_ids),
    )
    return ProjectionResult(pair=pair, reviewer_ids=frozenset(reviewer_ids))


def project_gad_extraction_v1(
    generation: AgentGeneration,
    corrections_by_criterion: dict[str, EffectiveCriterionCorrection],
) -> ProjectionResult:
    """Project generation with contract 'gad_extraction.v1'.

    Fact-only extraction; logs reason
    'gad_score_edit_ineligible_for_extraction_contract'.
    """
    return ProjectionResult(
        skip_reason="gad_score_edit_ineligible_for_extraction_contract"
    )


__all__ = [
    "ProjectionResult",
    "project_criterion_measurements_v1",
    "project_gad_extraction_v1",
    "project_itso_scores_v1",
]
