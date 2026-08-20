"""Typed state representations and reduction queries for reviewer feedback."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from server.modules.feedback.models import PreferenceLog
from sqlalchemy import func


@dataclass(frozen=True, slots=True)
class EffectiveCriterionCorrection:
    """Resolved effective correction state for an agent criterion."""

    log_id: uuid.UUID
    evaluation_id: uuid.UUID
    agent_name: str
    criterion_id: str
    action: Literal["EDIT", "REJECT"]
    score: int | None = None
    justification: str | None = None
    created_at: datetime | None = None
    user_id: uuid.UUID | None = None


def get_effective_criterion_corrections_batch(
    db: Any,
    evaluation_ids: Sequence[uuid.UUID],
    *,
    agent_names: Sequence[str] | None = None,
) -> dict[uuid.UUID, dict[tuple[str, str], EffectiveCriterionCorrection]]:
    """Return latest effective reviewer corrections grouped by evaluation_id.

    Reduces logs deterministically for each evaluation by ``(agent_name, criterion_id)``
    ordered by ``created_at DESC, log_id DESC``.

    Semantics:
    - Latest EDIT or REJECT creates an active overlay.
    - Latest ACCEPT creates no overlay (clears any older EDIT/REJECT).
    """
    eval_id_list = [eid for eid in evaluation_ids if eid is not None]
    if not eval_id_list:
        return {}

    query = db.query(PreferenceLog).filter(
        PreferenceLog.evaluation_id.in_(eval_id_list)
    )
    if agent_names is not None:
        names = [n.lower() for n in agent_names]
        query = query.filter(func.lower(PreferenceLog.agent_name).in_(names))

    logs: list[PreferenceLog] = (
        query.order_by(
            PreferenceLog.created_at.desc(),
            PreferenceLog.log_id.desc(),
        ).all()
    )

    latest_by_eval_and_key: dict[tuple[uuid.UUID, str, str], PreferenceLog] = {}
    for log in logs:
        if not log.evaluation_id or not log.agent_name or not log.criterion_id:
            continue
        key = (log.evaluation_id, log.agent_name, log.criterion_id)
        if key not in latest_by_eval_and_key:
            latest_by_eval_and_key[key] = log

    effective_by_eval: dict[
        uuid.UUID, dict[tuple[str, str], EffectiveCriterionCorrection]
    ] = defaultdict(dict)
    for (eval_id, agent_name, criterion_id), log in latest_by_eval_and_key.items():
        if log.action in ("EDIT", "REJECT"):
            edited = log.edited_json or {}
            effective_by_eval[eval_id][(agent_name, criterion_id)] = (
                EffectiveCriterionCorrection(
                    log_id=log.log_id,
                    evaluation_id=log.evaluation_id,
                    agent_name=agent_name,
                    criterion_id=criterion_id,
                    action=log.action,  # type: ignore[arg-type]
                    score=edited.get("score"),
                    justification=edited.get("justification"),
                    created_at=log.created_at,
                    user_id=log.user_id,
                )
            )

    return dict(effective_by_eval)


def get_effective_criterion_corrections(
    db: Any,
    evaluation_id: uuid.UUID,
    *,
    agent_names: Sequence[str] | None = None,
) -> dict[tuple[str, str], EffectiveCriterionCorrection]:
    """Return the latest effective reviewer corrections for an evaluation.

    Reduces logs deterministically by ``(agent_name, criterion_id)`` ordered by
    ``created_at DESC, log_id DESC``.

    Semantics:
    - Latest EDIT or REJECT creates an active overlay.
    - Latest ACCEPT creates no overlay (clears any older EDIT/REJECT).
    """
    if evaluation_id is None:
        return {}
    batch = get_effective_criterion_corrections_batch(
        db, [evaluation_id], agent_names=agent_names
    )
    return batch.get(evaluation_id, {})


__all__ = [
    "EffectiveCriterionCorrection",
    "get_effective_criterion_corrections",
    "get_effective_criterion_corrections_batch",
]
