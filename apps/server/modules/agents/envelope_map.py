"""Reconstruct which criteria belonged to which envelope for an evaluation.

SME and Coordinator each split a snapshot's criteria into at most 3
envelopes via their own ``pack_domains`` (envelope composition is
per-evaluation and dynamic, not a fixed global mapping -- see
``server/modules/agents/sme/packing.py``). Both functions are pure given
the snapshot's domains, so re-running them on a verified, loaded snapshot
deterministically reproduces the exact split used at scoring time, with
no extra persisted field required.
"""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.rubrics.contracts import CriterionDefinition
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO
from server.modules.rubrics.snapshots import load_verified_agent_snapshot

_SUPPORTED_AGENTS = ("sme", "coordinator")


def _pack_domains_for(agent_id: str):
    if agent_id == "sme":
        from server.modules.agents.sme.packing import pack_domains

        return pack_domains
    if agent_id == "coordinator":
        from server.modules.agents.coordinator.packing import pack_domains

        return pack_domains
    raise ValueError(
        f"envelope reconstruction is only supported for {_SUPPORTED_AGENTS}, "
        f"got '{agent_id}'"
    )


def envelope_criteria_map_from_snapshot(
    snapshot: EvaluationFormSnapshotDTO,
    agent_id: str,
) -> dict[str, tuple[CriterionDefinition, ...]]:
    """Pure version: reconstruct the envelope map from an already-loaded snapshot.

    Use this when the caller (e.g. evaluation_results.py) has already loaded
    and verified the snapshot, to avoid a redundant DB round trip. Raises
    ``ValueError`` if ``agent_id`` isn't a supported agent.
    """
    pack_domains = _pack_domains_for(agent_id)
    envelopes = pack_domains(snapshot.form.domains)
    return {f"envelope_{idx}": criteria for idx, criteria in enumerate(envelopes)}


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
    _pack_domains_for(agent_id)  # validate agent_id before any DB access

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
    "envelope_criteria_map_from_snapshot",
    "get_criterion_envelope_key",
    "get_envelope_criteria_map",
]
