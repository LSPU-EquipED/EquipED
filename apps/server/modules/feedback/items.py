"""Item-level (instance/qualifying-unit) correction support for the feedback module.

SME and Coordinator criteria using ``count_band``/``ratio_band`` never have
the LLM output a score directly -- it only lists raw extracted items
(instances, or units + which qualify), and code computes the score from
that list (see ``server/modules/agents/sme/scoring.py``). Correcting a
plain score for these criteria has no corresponding field in the model's
own output; the only signal that maps to real model behavior is which
extracted item was wrongly included or excluded. This module resolves
that per-item correction against the criterion's stored raw measurement
and recomputes the score using the same pure calculator the agent used.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from server.modules.agents.contracts import CriterionScore as AgentCriterionScore
from server.modules.agents.envelope_map import get_criterion_envelope_key
from server.modules.agents.sme.scoring import score_criterion_measurement
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    RatioBandConfig,
)
from server.modules.synthesis.models import AgentResult

from .exceptions import InvalidFeedbackTargetError
from .models import PreferenceLog

_ITEM_LEVEL_ACTIONS = ("ITEM_REJECT", "ITEM_ACCEPT")


@dataclass(frozen=True, slots=True)
class RawMeasurementItem:
    """One extracted item within a criterion's raw measurement, for display."""

    item_id: str
    text: str
    included: bool


def extract_raw_items(measurement: dict[str, Any]) -> tuple[RawMeasurementItem, ...]:
    """Return the display-ready item list for a count_band/ratio_band measurement.

    ``included`` reflects the model's own original output (before any
    reviewer correction is applied) -- for count_band every listed instance
    counts by definition; for ratio_band it depends on ``qualifying_unit_ids``.
    """
    if "instances" in measurement:
        return tuple(
            RawMeasurementItem(
                item_id=f"instance_{idx}", text=inst["excerpt"], included=True
            )
            for idx, inst in enumerate(measurement.get("instances") or [])
        )
    if "total_units" in measurement:
        qualifying = set(measurement.get("qualifying_unit_ids") or [])
        return tuple(
            RawMeasurementItem(
                item_id=unit["unit_id"],
                text=unit["evidence"],
                included=unit["unit_id"] in qualifying,
            )
            for unit in measurement.get("total_units") or []
        )
    raise InvalidFeedbackTargetError(
        "Measurement does not support item-level correction "
        "(neither 'instances' nor 'total_units' present)"
    )


def get_criterion_measurement(
    db: Any,
    evaluation_id: uuid.UUID,
    agent_name: str,
    criterion_id: str,
) -> dict[str, Any]:
    """Return the stored raw measurement dict for one criterion.

    Raises InvalidFeedbackTargetError if the agent result, envelope, or
    criterion measurement cannot be found.
    """
    result = (
        db.query(AgentResult)
        .filter_by(evaluation_id=evaluation_id, agent_name=agent_name)
        .first()
    )
    if result is None or not result.success or not result.group_responses:
        raise InvalidFeedbackTargetError(
            f"No successful '{agent_name}' result with stored responses "
            f"found for evaluation {evaluation_id}"
        )

    envelope_key = get_criterion_envelope_key(
        db, evaluation_id, agent_name, criterion_id
    )
    if envelope_key is None:
        raise InvalidFeedbackTargetError(
            f"Criterion '{criterion_id}' not found in the frozen snapshot "
            f"for agent '{agent_name}'"
        )

    envelope_response = result.group_responses.get(envelope_key)
    if not envelope_response:
        raise InvalidFeedbackTargetError(
            f"No stored response for envelope '{envelope_key}'"
        )

    for measurement in envelope_response.get("criterion_measurements", []):
        if measurement.get("criterion_id") == criterion_id:
            return measurement

    raise InvalidFeedbackTargetError(
        f"Criterion '{criterion_id}' not found in stored envelope response"
    )


def validate_item_id(measurement: dict[str, Any], item_id: str) -> None:
    """Raise InvalidFeedbackTargetError if item_id isn't in the measurement."""
    valid_ids = {item.item_id for item in extract_raw_items(measurement)}
    if item_id not in valid_ids:
        raise InvalidFeedbackTargetError(
            f"item_id '{item_id}' not found in this criterion's extracted items"
        )


def get_effective_item_rejections(
    db: Any,
    evaluation_id: uuid.UUID,
    agent_name: str,
    criterion_id: str,
) -> frozenset[str]:
    """Return the set of currently-rejected item_ids for one criterion.

    Reduces ITEM_REJECT/ITEM_ACCEPT logs by item_id, latest wins (ties
    broken by log_id desc), matching the reduction semantics used for
    criterion-level corrections in feedback/state.py.
    """
    logs: list[PreferenceLog] = (
        db.query(PreferenceLog)
        .filter(
            PreferenceLog.evaluation_id == evaluation_id,
            PreferenceLog.agent_name == agent_name,
            PreferenceLog.criterion_id == criterion_id,
            PreferenceLog.action.in_(_ITEM_LEVEL_ACTIONS),
            PreferenceLog.item_id.isnot(None),
        )
        .order_by(PreferenceLog.created_at.desc(), PreferenceLog.log_id.desc())
        .all()
    )

    latest_by_item: dict[str, PreferenceLog] = {}
    for log in logs:
        if log.item_id not in latest_by_item:
            latest_by_item[log.item_id] = log

    return frozenset(
        item_id
        for item_id, log in latest_by_item.items()
        if log.action == "ITEM_REJECT"
    )


def get_effective_item_rejections_batch(
    db: Any,
    evaluation_id: uuid.UUID,
    agent_names: tuple[str, ...],
) -> dict[tuple[str, str], frozenset[str]]:
    """Batch version of get_effective_item_rejections for one evaluation.

    Returns ``{(agent_name, criterion_id): frozenset(rejected_item_ids)}``,
    one query instead of one per criterion -- for use by the evaluation
    results assembly, which needs this for every criterion at once.
    """
    logs: list[PreferenceLog] = (
        db.query(PreferenceLog)
        .filter(
            PreferenceLog.evaluation_id == evaluation_id,
            PreferenceLog.agent_name.in_(agent_names),
            PreferenceLog.action.in_(_ITEM_LEVEL_ACTIONS),
            PreferenceLog.item_id.isnot(None),
        )
        .order_by(PreferenceLog.created_at.desc(), PreferenceLog.log_id.desc())
        .all()
    )

    latest_by_key: dict[tuple[str, str, str], PreferenceLog] = {}
    for log in logs:
        key = (log.agent_name, log.criterion_id, log.item_id)
        if key not in latest_by_key:
            latest_by_key[key] = log

    rejections: dict[tuple[str, str], set[str]] = {}
    for (agent_name, criterion_id, item_id), log in latest_by_key.items():
        if log.action == "ITEM_REJECT":
            rejections.setdefault((agent_name, criterion_id), set()).add(item_id)

    return {key: frozenset(ids) for key, ids in rejections.items()}


def apply_item_rejections(
    measurement: dict[str, Any], rejected_item_ids: frozenset[str]
) -> dict[str, Any]:
    """Return a corrected measurement dict with rejected items applied.

    count_band: rejected instances are removed from the list entirely.
    ratio_band: rejected units are removed from qualifying_unit_ids (the
    unit stays listed in total_units -- it just no longer counts).
    """
    if not rejected_item_ids:
        return measurement

    if "instances" in measurement:
        kept = [
            inst
            for idx, inst in enumerate(measurement.get("instances") or [])
            if f"instance_{idx}" not in rejected_item_ids
        ]
        return {**measurement, "instances": kept}

    if "total_units" in measurement:
        qualifying = [
            uid
            for uid in measurement.get("qualifying_unit_ids") or []
            if uid not in rejected_item_ids
        ]
        return {**measurement, "qualifying_unit_ids": qualifying}

    return measurement


def get_corrected_criterion_score(
    db: Any,
    evaluation_id: uuid.UUID,
    agent_name: str,
    criterion_id: str,
    criterion_definition: CriterionDefinition,
) -> AgentCriterionScore | None:
    """Recompute a criterion's score from its item-level corrections, if any.

    Returns None if the criterion isn't item-correctable (not count_band/
    ratio_band) or has no active item rejections -- callers should fall
    back to the originally persisted CriterionScore in that case.
    """
    if not isinstance(
        criterion_definition.strategy_config, (CountBandConfig, RatioBandConfig)
    ):
        return None

    rejected = get_effective_item_rejections(
        db, evaluation_id, agent_name, criterion_id
    )
    if not rejected:
        return None

    measurement = get_criterion_measurement(db, evaluation_id, agent_name, criterion_id)
    corrected_measurement = apply_item_rejections(measurement, rejected)
    return score_criterion_measurement(criterion_definition, corrected_measurement)


__all__ = [
    "RawMeasurementItem",
    "apply_item_rejections",
    "extract_raw_items",
    "get_corrected_criterion_score",
    "get_criterion_measurement",
    "get_effective_item_rejections",
    "get_effective_item_rejections_batch",
    "validate_item_id",
]
