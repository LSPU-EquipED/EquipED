"""DPO training pair projection for SME/Coordinator feedback.

Two independent export paths, depending on whether the LLM outputs the
score itself for a given criterion:

- export_score_level_dpo_pairs: for llm_rubric_guidance criteria (SME and
  Coordinator's OP-01..OP-05/A-01..A-04, since both were converted from
  count_band/ratio_band -- see convert_sme_to_llm_rubric_guidance.py and
  convert_coordinator_to_llm_rubric_guidance.py). The model states its
  own score, so a plain score+justification EDIT is real model output to
  pair against.
- export_item_level_dpo_pairs: for any remaining count_band/ratio_band
  criteria, where the LLM never outputs a score directly (code computes
  it from an extracted item list) -- a score-only correction has no
  field in the model's own output to attach to, so only ITEM_REJECT/
  ITEM_ACCEPT corrections on the item list itself are valid pairs. See
  server/modules/feedback/items.py for that correction/recompute
  mechanism. As of the conversions above, this path is currently dormant
  for SME/Coordinator (no criteria left in that shape) but is kept for
  any future/other agent still using those strategies.

Pairs are keyed per (evaluation, envelope): an envelope with no active
correction among its criteria yields no pair -- no real agent call ever
produces a "corrected" response for an envelope nobody touched, and a
synthetic one would train on a shape the model never sees at inference.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from server.modules.agents.envelope_map import get_envelope_criteria_map
from server.modules.synthesis.models import AgentResult

from .items import apply_item_rejections
from .models import PreferenceLog
from .state import get_effective_criterion_corrections

logger = logging.getLogger(__name__)

_ITEM_LEVEL_AGENTS = ("sme", "coordinator")
_ITEM_LEVEL_ACTIONS = ("ITEM_REJECT", "ITEM_ACCEPT")
_SCORE_LEVEL_AGENTS = ("sme", "coordinator")


@dataclass(frozen=True, slots=True)
class DpoPair:
    """One envelope's DPO training pair: full-response chosen vs. rejected."""

    prompt: str
    chosen: str
    rejected: str
    evaluation_id: uuid.UUID
    document_id: uuid.UUID
    reviewer_ids: frozenset[uuid.UUID]


def _effective_rejections_with_reviewers(
    db: Any, evaluation_id: uuid.UUID, agent_name: str
) -> dict[str, tuple[frozenset[str], frozenset[uuid.UUID]]]:
    """Return {criterion_id: (rejected_item_ids, reviewer_ids)} for one
    evaluation/agent.

    Reduces ITEM_REJECT/ITEM_ACCEPT logs by (criterion_id, item_id), latest
    wins (ties broken by log_id desc) -- same semantics as
    feedback/items.py's get_effective_item_rejections, but also tracks
    which user made each effective rejection, needed for DPO provenance.
    """
    logs: list[PreferenceLog] = (
        db.query(PreferenceLog)
        .filter(
            PreferenceLog.evaluation_id == evaluation_id,
            PreferenceLog.agent_name == agent_name,
            PreferenceLog.action.in_(_ITEM_LEVEL_ACTIONS),
            PreferenceLog.item_id.isnot(None),
        )
        .order_by(PreferenceLog.created_at.desc(), PreferenceLog.log_id.desc())
        .all()
    )

    latest_by_key: dict[tuple[str, str], PreferenceLog] = {}
    for log in logs:
        key = (log.criterion_id, log.item_id)
        if key not in latest_by_key:
            latest_by_key[key] = log

    rejected_items: dict[str, set[str]] = defaultdict(set)
    reviewers: dict[str, set[uuid.UUID]] = defaultdict(set)
    for (criterion_id, item_id), log in latest_by_key.items():
        if log.action == "ITEM_REJECT":
            rejected_items[criterion_id].add(item_id)
            reviewers[criterion_id].add(log.user_id)

    return {
        criterion_id: (frozenset(items), frozenset(reviewers[criterion_id]))
        for criterion_id, items in rejected_items.items()
    }


def export_item_level_dpo_pairs(
    db: Any, agent_names: tuple[str, ...]
) -> Iterator[DpoPair]:
    """Yield one DpoPair per envelope with an active item-level correction."""
    if len(agent_names) != 1:
        raise ValueError(
            "DPO exports require exactly one target agent to prevent dataset "
            f"contamination, got {agent_names}"
        )
    candidate_rows = (
        db.query(PreferenceLog.evaluation_id, PreferenceLog.agent_name)
        .filter(
            PreferenceLog.agent_name.in_(agent_names),
            PreferenceLog.action.in_(_ITEM_LEVEL_ACTIONS),
            PreferenceLog.item_id.isnot(None),
        )
        .distinct()
        .all()
    )

    for evaluation_id, agent_name in candidate_rows:
        result = (
            db.query(AgentResult)
            .filter_by(evaluation_id=evaluation_id, agent_name=agent_name)
            .first()
        )
        if result is None or not result.success or not result.group_responses:
            continue

        corrections_by_criterion = _effective_rejections_with_reviewers(
            db, evaluation_id, agent_name
        )
        corrections_by_criterion = {
            cid: (items, reviewers)
            for cid, (items, reviewers) in corrections_by_criterion.items()
            if items
        }
        if not corrections_by_criterion:
            continue

        try:
            envelope_map = get_envelope_criteria_map(db, evaluation_id, agent_name)
        except Exception:
            logger.warning(
                "Failed to get envelope criteria map for evaluation %s agent %s",
                evaluation_id,
                agent_name,
                exc_info=True,
            )
            continue

        code_to_envelope_key = {
            c.criterion_code: key
            for key, criteria in envelope_map.items()
            for c in criteria
        }

        envelopes_touched: dict[str, set[str]] = defaultdict(set)
        for criterion_id in corrections_by_criterion:
            env_key = code_to_envelope_key.get(criterion_id)
            if env_key is not None:
                envelopes_touched[env_key].add(criterion_id)

        for env_key, criterion_ids in envelopes_touched.items():
            status = (result.envelope_status or {}).get(env_key, "ok")
            if status != "ok":
                logger.warning(
                    "Skipping envelope %s for evaluation %s agent %s: "
                    "status is '%s' (not 'ok')",
                    env_key,
                    evaluation_id,
                    agent_name,
                    status,
                )
                continue

            prompt = (result.group_prompts or {}).get(env_key)
            envelope_response = (result.group_responses or {}).get(env_key)
            if not prompt or not envelope_response:
                continue

            measurements = envelope_response.get("criterion_measurements", [])
            chosen_measurements = []
            reviewer_ids: set[uuid.UUID] = set()
            real_change = False
            for measurement in measurements:
                cid = measurement.get("criterion_id")
                if cid in criterion_ids:
                    rejected_items, reviewers = corrections_by_criterion[cid]
                    corrected = apply_item_rejections(measurement, rejected_items)
                    if corrected != measurement:
                        real_change = True
                    reviewer_ids.update(reviewers)
                    chosen_measurements.append(corrected)
                else:
                    chosen_measurements.append(measurement)

            if not real_change:
                continue

            chosen_response = {
                **envelope_response,
                "criterion_measurements": chosen_measurements,
            }

            yield DpoPair(
                prompt=prompt,
                chosen=json.dumps(chosen_response, ensure_ascii=False),
                rejected=json.dumps(envelope_response, ensure_ascii=False),
                evaluation_id=evaluation_id,
                document_id=result.document_id,
                reviewer_ids=frozenset(reviewer_ids),
            )


def _is_score_shaped(measurement: dict[str, Any]) -> bool:
    """True only for a genuine llm_rubric_guidance measurement.

    Guards against ever substituting a score into a count_band/ratio_band
    measurement (no "score" field there by design -- see
    server/modules/agents/sme/response.py's score-field blocklist) --
    relevant for historical SME evaluations scored before the criteria
    were converted to llm_rubric_guidance, and for other agents (e.g.
    Coordinator) still on the calculator strategies.
    """
    return (
        "score" in measurement
        and "instances" not in measurement
        and "total_units" not in measurement
    )


def export_score_level_dpo_pairs(
    db: Any, agent_names: tuple[str, ...]
) -> Iterator[DpoPair]:
    """Yield one DpoPair per envelope with an active score-level EDIT.

    Applies only to llm_rubric_guidance criteria, where the LLM outputs
    the score itself -- see server/modules/agents/sme/prompt.py. A plain
    score+justification correction (the EDIT action) is real, valid model
    output to pair against for these criteria, unlike SME/Coordinator's
    count_band/ratio_band criteria (see export_item_level_dpo_pairs).

    An envelope with any effective REJECT among its criteria is skipped
    entirely: REJECT carries no corrected score/justification to build a
    "chosen" response from.
    """
    if len(agent_names) != 1:
        raise ValueError(
            "DPO exports require exactly one target agent to prevent dataset "
            f"contamination, got {agent_names}"
        )
    candidate_rows = (
        db.query(PreferenceLog.evaluation_id, PreferenceLog.agent_name)
        .filter(
            PreferenceLog.agent_name.in_(agent_names),
            PreferenceLog.action == "EDIT",
        )
        .distinct()
        .all()
    )

    for evaluation_id, agent_name in candidate_rows:
        result = (
            db.query(AgentResult)
            .filter_by(evaluation_id=evaluation_id, agent_name=agent_name)
            .first()
        )
        if result is None or not result.success or not result.group_responses:
            continue

        corrections = get_effective_criterion_corrections(
            db, evaluation_id, agent_names=[agent_name]
        )
        edit_corrections = {
            criterion_id: corr
            for (a, criterion_id), corr in corrections.items()
            if a == agent_name
        }
        if not edit_corrections:
            continue

        try:
            envelope_map = get_envelope_criteria_map(db, evaluation_id, agent_name)
        except Exception:
            logger.warning(
                "Failed to get envelope criteria map for evaluation %s agent %s",
                evaluation_id,
                agent_name,
                exc_info=True,
            )
            continue

        code_to_envelope_key = {
            c.criterion_code: key
            for key, criteria in envelope_map.items()
            for c in criteria
        }

        envelopes_touched: dict[str, dict[str, Any]] = defaultdict(dict)
        for criterion_id, corr in edit_corrections.items():
            env_key = code_to_envelope_key.get(criterion_id)
            if env_key is not None:
                envelopes_touched[env_key][criterion_id] = corr

        for env_key, crit_corrections in envelopes_touched.items():
            # A REJECT in this envelope has no corrected text -- can't
            # build a "chosen" response for the whole envelope.
            if any(corr.action == "REJECT" for corr in crit_corrections.values()):
                continue

            status = (result.envelope_status or {}).get(env_key, "ok")
            if status != "ok":
                logger.warning(
                    "Skipping envelope %s for evaluation %s agent %s: "
                    "status is '%s' (not 'ok')",
                    env_key,
                    evaluation_id,
                    agent_name,
                    status,
                )
                continue

            prompt = (result.group_prompts or {}).get(env_key)
            envelope_response = (result.group_responses or {}).get(env_key)
            if not prompt or not envelope_response:
                continue

            measurements = envelope_response.get("criterion_measurements", [])
            chosen_measurements = []
            reviewer_ids: set[uuid.UUID] = set()
            real_change = False
            skip_envelope = False

            for measurement in measurements:
                cid = measurement.get("criterion_id")
                corr = crit_corrections.get(cid)
                if corr is None or corr.action != "EDIT":
                    chosen_measurements.append(measurement)
                    continue

                if not _is_score_shaped(measurement):
                    logger.warning(
                        "Skipping envelope %s for evaluation %s: criterion "
                        "'%s' has a score-level EDIT but its stored "
                        "measurement isn't llm_rubric_guidance-shaped",
                        env_key,
                        evaluation_id,
                        cid,
                    )
                    skip_envelope = True
                    break

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

            if skip_envelope or not real_change:
                continue

            chosen_response = {
                **envelope_response,
                "criterion_measurements": chosen_measurements,
            }

            yield DpoPair(
                prompt=prompt,
                chosen=json.dumps(chosen_response, ensure_ascii=False),
                rejected=json.dumps(envelope_response, ensure_ascii=False),
                evaluation_id=evaluation_id,
                document_id=result.document_id,
                reviewer_ids=frozenset(reviewer_ids),
            )


__all__ = [
    "DpoPair",
    "export_item_level_dpo_pairs",
    "export_score_level_dpo_pairs",
]
