"""Historical v3/v4 saved results remain readable and tamper evident."""

from __future__ import annotations

import copy
from dataclasses import replace

import pytest
from historical_fixture import load_historical_fixture

_SUMMARIES = {
    3: (
        "OP-01: No topic transitions were identified in the reviewed text. "
        "The extracted material did not demonstrate op-01. OP-02: No "
        "interactive tasks were identified in the reviewed text. The extracted "
        "material did not demonstrate op-02. A-01: The task asks learners "
        "to demonstrate a distinct assessment practice with a concrete response. "
        "Naming a type checks recall but does not ask learners to apply or analyze "
        "it. A-05: The quoted task directly assesses the requested skill and concept."
    ),
    4: (
        "The reviewed evidence supports several assessment practices, with "
        "progress monitoring still unestablished."
    ),
}


@pytest.mark.parametrize("version", [3, 4])
def test_historical_fixture_preserves_snapshot_and_result_contract(version):
    snapshot, result = load_historical_fixture(version)
    assert snapshot.agent_id == "coordinator"
    assert snapshot.evaluation_id == result.evaluation_id
    assert snapshot.snapshot_hash
    assert result.success
    assert result.generations == ()
    assert result.metadata["execution_contract"] == f"coordinator_current.v{version}"
    responses = result.metadata["group_responses"]
    assert responses
    assert len(result.criterion_scores) == 10
    expected_ids = {
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
    }
    for score in result.criterion_scores:
        assert score.criterion_id in expected_ids
        assert score.score in range(1, 5)
        assert score.justification.strip()
    assert result.summary.strip()
    assert result.metadata["current_bundle"]["criteria"]
    _assert_historical_integrity(snapshot, result, version=version)


@pytest.mark.parametrize(
    "version,mutation",
    [
        (version, mutation)
        for version in (3, 4)
        for mutation in ("group", "score", "evidence", "snapshot")
    ]
    + [(4, "summary")],
)
def test_historical_fixture_tampering_is_detected(version, mutation):
    snapshot, result = load_historical_fixture(version)
    if mutation == "group":
        altered = copy.deepcopy(result.metadata)
        altered["group_responses"].pop(
            "finding-A-02" if version == 4 else "ordinary-A-02"
        )
        result = replace(result, metadata=altered)
    elif mutation == "summary":
        result = replace(result, summary="Changed historical summary.")
    elif mutation == "score":
        result = replace(
            result,
            criterion_scores=tuple(
                replace(score, score=1) if score.criterion_id == "A-02" else score
                for score in result.criterion_scores
            ),
        )
    elif mutation == "evidence":
        result = replace(
            result,
            criterion_scores=tuple(
                replace(score, evidence=("invented evidence",))
                if score.criterion_id == "A-02"
                else score
                for score in result.criterion_scores
            ),
        )
    else:
        snapshot = snapshot.model_copy(update={"evaluation_id": result.document_id})
    with pytest.raises(ValueError):
        _assert_historical_integrity(snapshot, result, version=version)


def _assert_historical_integrity(snapshot, result, *, version):
    """Exercise the actual production reader, including exact frozen wording."""
    from equiped_harness.agents.coordinator.validation import (
        validate_current_coordinator_bundle,
    )
    from equiped_harness.contracts.snapshots import compute_snapshot_hash

    if snapshot.evaluation_id != result.evaluation_id:
        raise ValueError("snapshot identity changed")
    if snapshot.snapshot_hash != compute_snapshot_hash(snapshot.snapshot_payload):
        raise ValueError("historical snapshot hash changed")
    if result.summary != _SUMMARIES[version]:
        raise ValueError("historical summary differs from the frozen fixture")
    metadata = copy.deepcopy(result.metadata)
    metadata["group_responses"]["__current_bundle__"] = metadata["current_bundle"]
    validate_current_coordinator_bundle(replace(result, metadata=metadata), snapshot)
