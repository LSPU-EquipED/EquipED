"""Reconstruct which criteria belonged to which envelope for an evaluation.

SME and Coordinator each split a snapshot's criteria into at most 3
envelopes via their own ``pack_domains`` (envelope composition is
per-evaluation and dynamic, not a fixed global mapping -- see
``equiped_harness.agents.sme.packing``). Both functions are pure given
the snapshot's domains, so re-running them on a verified, loaded snapshot
deterministically reproduces the exact split used at scoring time, with
no extra persisted field required.
"""

from __future__ import annotations

import uuid
from typing import Any

from equiped_harness import envelope_criteria_map_from_snapshot
from equiped_harness.contracts import CriterionDefinition

from server.modules.rubrics.snapshots import load_verified_agent_snapshot


def get_envelope_criteria_map(
    db: Any,
    evaluation_id: uuid.UUID,
    agent_id: str,
) -> dict[str, tuple[CriterionDefinition, ...]]:
    """Return ``{"envelope_0": (criteria...), ...}`` for one evaluation/agent.

    Raises ``SnapshotIntegrityError`` (propagated) if the snapshot cannot be
    loaded and verified, and ``ValueError`` if ``agent_id`` isn't one of the
    agents whose envelope packing this module knows how to reconstruct.
    """
    if agent_id not in {"sme", "coordinator"}:
        raise ValueError(
            "envelope reconstruction is only supported for sme and coordinator"
        )

    snapshot = load_verified_agent_snapshot(db, evaluation_id, agent_id)
    return envelope_criteria_map_from_snapshot(snapshot, agent_id)


def get_criterion_envelope_key(
    db: Any,
    evaluation_id: uuid.UUID,
    agent_id: str,
    criterion_id: str,
) -> str | None:
    """Return the envelope key containing ``criterion_id``, or None if absent."""
    envelope_map = get_envelope_criteria_map(db, evaluation_id, agent_id)
    for env_key, criteria in envelope_map.items():
        if any(c.criterion_code == criterion_id for c in criteria):
            return env_key
    return None


__all__ = [
    "get_criterion_envelope_key",
    "get_envelope_criteria_map",
]
