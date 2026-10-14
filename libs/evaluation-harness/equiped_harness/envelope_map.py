"""Deterministic snapshot envelope reconstruction."""

from .contracts import CriterionDefinition
from .snapshot_contracts import EvaluationFormSnapshotDTO

_SUPPORTED_AGENTS = ("sme", "coordinator")


def _pack_domains_for(agent_id: str):
    if agent_id == "sme":
        from equiped_harness.sme.packing import pack_domains

        return pack_domains
    if agent_id == "coordinator":
        from equiped_harness.coordinator.packing import pack_domains

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


__all__ = ["envelope_criteria_map_from_snapshot"]
