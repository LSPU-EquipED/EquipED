"""Capability registry for agent response contracts and DPO projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ContractCapability:
    """Declared capabilities of a response contract version."""

    contract_key: str
    version: int
    supports_score_edit: bool
    supports_item_rejection: bool
    skip_reason: str | None = None


_CAPABILITIES: Final[dict[tuple[str, int], ContractCapability]] = {
    ("criterion_measurements.v1", 1): ContractCapability(
        contract_key="criterion_measurements.v1",
        version=1,
        supports_score_edit=True,
        supports_item_rejection=True,
        skip_reason=None,
    ),
    ("gad_extraction.v1", 1): ContractCapability(
        contract_key="gad_extraction.v1",
        version=1,
        supports_score_edit=False,
        supports_item_rejection=False,
        skip_reason="gad_score_edit_ineligible_for_extraction_contract",
    ),
    ("itso_scores.v1", 1): ContractCapability(
        contract_key="itso_scores.v1",
        version=1,
        supports_score_edit=True,
        supports_item_rejection=False,
        skip_reason=None,
    ),
    ("gad_scores.v1", 1): ContractCapability(
        contract_key="gad_scores.v1",
        version=1,
        supports_score_edit=True,
        supports_item_rejection=False,
        skip_reason=None,
    ),
}


def get_contract_capability(contract_key: str, version: int = 1) -> ContractCapability:
    """Retrieve capabilities for a given response contract key and version.

    If not found in registry, returns a default non-supported capability.
    """
    cap = _CAPABILITIES.get((contract_key, version))
    if cap is not None:
        return cap
    return ContractCapability(
        contract_key=contract_key,
        version=version,
        supports_score_edit=False,
        supports_item_rejection=False,
        skip_reason=f"unsupported_contract_{contract_key}_v{version}",
    )


__all__ = [
    "ContractCapability",
    "get_contract_capability",
]
