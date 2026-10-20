"""Pure ITSO policy plan and snapshot interpretation contracts."""

from equiped_harness.agents.itso.policy import ITSO_POLICY_MAP
from equiped_harness.contracts.references import (
    PolicyEvidenceChunk,
    PolicyRetrievalResult,
)
from equiped_harness.policy import format_policy_snapshot, get_policy_plan


def test_policy_plan_is_specialist_owned_and_facade_is_lazy():
    plan = get_policy_plan("itso", 3)
    assert plan is not None
    assert plan.agent_id == "itso"
    assert plan.adapter_version == 3
    assert dict(plan.criteria_areas) == ITSO_POLICY_MAP
    assert get_policy_plan("gad", 2) is None


def test_policy_snapshot_preserves_evidence_and_opaque_provenance():
    plan = get_policy_plan("itso", 3)
    assert plan is not None
    chunks = (
        PolicyEvidenceChunk(
            "chunk-id", "doc-id", "policy clause", "data_privacy", 4, 8, 0.2
        ),
    )
    result = PolicyRetrievalResult("data_privacy", "available", chunks, "b" * 64)
    projected = format_policy_snapshot(
        plan,
        {"ITSO-04": result},
        delivery_state="enabled",
    )
    assert projected["evidence"]["criteria"]["ITSO-04"] == {
        "policy_area": "data_privacy",
        "status": "available",
        "chunks": [
            {
                "chunk_id": "chunk-id",
                "text": "policy clause",
                "page_number": 4,
                "policy_area": "data_privacy",
            }
        ],
    }
    assert projected["provenance"]["ITSO-04"] == {
        "status": "available",
        "chunk_count": 1,
        "provenance_hash": "b" * 64,
    }
    assert projected["provenance"]["ITSO-03"]["chunk_count"] == 0
