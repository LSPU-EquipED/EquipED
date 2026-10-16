"""Read stored criterion explanations without reconstructing model reasoning."""

from __future__ import annotations

import json
import uuid
from typing import Any

from server.modules.synthesis.models import AgentGeneration, AgentResult, CriterionScore

from .schemas import ModelValidationCriterionExplanationResponse


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _evidence(value: Any) -> list[str] | None:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            decoded = None
        value = decoded if isinstance(decoded, list) else [value]
    if not isinstance(value, list):
        return None
    return [item for item in value if _text(item)] or None


def _measurement(generation: AgentGeneration, code: str) -> dict | None:
    payload = generation.response_json
    if not isinstance(payload, dict):
        try:
            payload = json.loads(generation.response_text)
        except (ValueError, TypeError):
            return None
    if not isinstance(payload, dict):
        return None
    measurements = payload.get("criterion_measurements")
    if isinstance(measurements, list):
        matches = [
            item
            for item in measurements
            if isinstance(item, dict) and item.get("criterion_id") == code
        ]
    else:
        matches = [
            value
            for key, value in payload.items()
            if key.casefold() == code.casefold() and isinstance(value, dict)
        ]
    return matches[0] if len(matches) == 1 else None


def get_criterion_explanations(
    db: Any, evaluation_id: uuid.UUID
) -> dict[tuple[str, str], ModelValidationCriterionExplanationResponse]:
    """Two bounded reads for one detail view; list/metrics calls stay lightweight."""
    rows = (
        db.query(CriterionScore, AgentResult)
        .join(
            AgentResult, AgentResult.agent_result_id == CriterionScore.agent_result_id
        )
        .filter(CriterionScore.evaluation_id == evaluation_id)
        .all()
    )
    generations = (
        db.query(AgentGeneration)
        .filter(AgentGeneration.evaluation_id == evaluation_id)
        .all()
    )
    by_criterion: dict[tuple[uuid.UUID, str], list[AgentGeneration]] = {}
    for generation in generations:
        for code in generation.criterion_ids or []:
            by_criterion.setdefault((generation.agent_result_id, code), []).append(
                generation
            )

    explanations = {}
    for score, result in rows:
        candidates = by_criterion.get((result.agent_result_id, score.criterion_id), [])
        generation = candidates[0] if len(candidates) == 1 else None
        status = generation.envelope_status if generation is not None else "unavailable"
        if status not in {"ok", "repaired", "fallback"}:
            status = "unavailable"
        measurement = (
            _measurement(generation, score.criterion_id)
            if generation is not None and status in {"ok", "repaired"}
            else None
        )
        explanations[(result.agent_name, score.criterion_id)] = (
            ModelValidationCriterionExplanationResponse(
                status=status,
                model_name=_text(
                    generation.model_name if generation else result.model_name
                ),
                evidence=(
                    _evidence(measurement.get("evidence")) if measurement else None
                )
                or _evidence(score.evidence),
                reasoning=_text(measurement.get("reasoning")) if measurement else None,
                stored_justification=_text(score.justification),
            )
        )
    return explanations
