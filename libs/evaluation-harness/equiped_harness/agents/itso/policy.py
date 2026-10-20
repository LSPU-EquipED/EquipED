"""ITSO policy mapping and portable snapshot interpretation."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from equiped_harness.contracts.references import (
    PolicyRetrievalPlan,
    PolicyRetrievalResult,
)

ITSO_POLICY_MAP: dict[str, tuple[str, ...]] = {
    "ITSO-03": ("intellectual_property", "general_itso"),
    "ITSO-04": ("data_privacy", "general_itso"),
    "ITSO-05": ("academic_rights", "general_itso"),
}
ITSO_POLICY_QUERY = (
    "information security data privacy intellectual property academic rights"
)
POLICY_RETRIEVAL_VERSION = "1"


def get_itso_policy_plan(adapter_version: int) -> PolicyRetrievalPlan:
    return PolicyRetrievalPlan(
        agent_id="itso",
        adapter_version=adapter_version,
        criteria_areas=dict(ITSO_POLICY_MAP),
        query_text=ITSO_POLICY_QUERY,
        retrieval_version=POLICY_RETRIEVAL_VERSION,
    )


def build_policy_snapshot(
    plan: PolicyRetrievalPlan,
    results: Mapping[str, PolicyRetrievalResult | None],
    *,
    delivery_state: str,
) -> dict[str, Any]:
    """Project portable retrieval outcomes to ITSO prompt and provenance data."""
    evidence: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    empty_hash = hashlib.sha256(b"empty").hexdigest()
    for criterion_id, areas in plan.criteria_areas.items():
        result = results.get(criterion_id)
        area = areas[0] if areas else "unknown"
        if result is not None and result.status == "available":
            evidence[criterion_id] = {
                "policy_area": area,
                "status": "available",
                "chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "page_number": chunk.page_number,
                        "policy_area": chunk.policy_area,
                    }
                    for chunk in result.chunks
                ],
            }
            provenance[criterion_id] = {
                "status": "available",
                "chunk_count": result.chunk_count,
                "provenance_hash": result.provenance_hash,
            }
        else:
            evidence[criterion_id] = {
                "policy_area": area,
                "status": "unavailable",
                "chunks": [],
            }
            provenance[criterion_id] = {
                "status": "unavailable",
                "chunk_count": 0,
                "provenance_hash": (
                    result.provenance_hash if result is not None else empty_hash
                ),
            }
    return {
        "evidence": {
            "delivery_state": delivery_state,
            "retrieval_version": plan.retrieval_version,
            "criteria": evidence,
        },
        "provenance": provenance,
        "delivery_state": delivery_state,
        "retrieval_version": plan.retrieval_version,
    }


def empty_policy_snapshot(
    plan: PolicyRetrievalPlan, *, status: str, delivery_state: str
) -> dict[str, Any]:
    empty_hash = hashlib.sha256(b"empty").hexdigest()
    return {
        "evidence": None,
        "provenance": {
            criterion_id: {
                "status": status,
                "chunk_count": 0,
                "provenance_hash": empty_hash,
            }
            for criterion_id in plan.criteria_areas
        },
        "delivery_state": delivery_state,
        "retrieval_version": plan.retrieval_version,
    }


__all__ = [
    "ITSO_POLICY_MAP",
    "ITSO_POLICY_QUERY",
    "POLICY_RETRIEVAL_VERSION",
    "build_policy_snapshot",
    "empty_policy_snapshot",
    "get_itso_policy_plan",
]
