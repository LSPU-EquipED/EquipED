"""Item-level DPO training pair projection for SME/Coordinator feedback.

Only item-level corrections (ITEM_REJECT/ITEM_ACCEPT) produce valid DPO
pairs today: SME/Coordinator's count_band/ratio_band criteria never have
the LLM output a score directly, so a score-only correction (EDIT/REJECT)
has no corresponding field in the model's own output to pair against. See
server/modules/feedback/items.py for the correction/recompute mechanism
this module builds on.

Pairs are keyed per (evaluation, envelope): an envelope with no active
item rejection among its criteria yields no pair -- no real agent call
ever produces a "corrected" response for an envelope nobody touched, and
a synthetic one would train on a shape the model never sees at inference.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from server.modules.agents.envelope_map import get_envelope_criteria_map
from server.modules.synthesis.models import AgentResult

from .items import apply_item_rejections
from .models import PreferenceLog

_ITEM_LEVEL_AGENTS = ("sme", "coordinator")
_ITEM_LEVEL_ACTIONS = ("ITEM_REJECT", "ITEM_ACCEPT")


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


def export_item_level_dpo_pairs(db: Any) -> Iterator[DpoPair]:
    """Yield one DpoPair per envelope with an active item-level correction."""
    candidate_rows = (
        db.query(PreferenceLog.evaluation_id, PreferenceLog.agent_name)
        .filter(
            PreferenceLog.agent_name.in_(_ITEM_LEVEL_AGENTS),
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


__all__ = ["DpoPair", "export_item_level_dpo_pairs"]
