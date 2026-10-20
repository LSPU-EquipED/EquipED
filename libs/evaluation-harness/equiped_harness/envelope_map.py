"""Deterministic snapshot envelope reconstruction."""

from equiped_harness.contracts import CriterionDefinition
from equiped_harness.contracts.snapshots import EvaluationFormSnapshotDTO

_SUPPORTED_AGENTS = ("sme", "coordinator")


def _pack_domains_for(agent_id: str):
    if agent_id == "sme":
        from equiped_harness.agents.sme.packing import pack_domains

        return pack_domains
    if agent_id == "coordinator":
        from equiped_harness.agents.coordinator.packing import pack_domains

        return pack_domains
    raise ValueError(
        f"envelope reconstruction is only supported for {_SUPPORTED_AGENTS}, "
        f"got '{agent_id}'"
    )


def envelope_criteria_map_from_snapshot(
    snapshot: EvaluationFormSnapshotDTO,
    agent_id: str,
    execution_contract: str | None = None,
) -> dict[str, tuple[CriterionDefinition, ...]]:
    """Pure version: reconstruct the envelope map from an already-loaded snapshot.

    Use this when the caller (e.g. evaluation_results.py) has already loaded
    and verified the snapshot, to avoid a redundant DB round trip. Raises
    ``ValueError`` if ``agent_id`` isn't a supported agent.
    """
    criteria = tuple(c for d in snapshot.form.domains for c in d.criteria)
    if agent_id == "coordinator" and execution_contract == "coordinator_current.v1":
        groups = {
            f"ordinary-{c.criterion_code}": (c,)
            for c in criteria
            if (c.criterion_code.startswith("OP-") or c.criterion_code.startswith("A-"))
            and c.criterion_code != "A-05"
        }
        a05 = tuple(c for c in criteria if c.criterion_code == "A-05")
        if a05:
            groups["objective-assessment"] = a05
        return groups
    pack_domains = _pack_domains_for(agent_id)
    envelopes = pack_domains(snapshot.form.domains)
    return {f"envelope_{idx}": criteria for idx, criteria in enumerate(envelopes)}


__all__ = ["envelope_criteria_map_from_snapshot"]
