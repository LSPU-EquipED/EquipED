"""Saved Coordinator v5 results remain bound to their packet and narratives."""

from __future__ import annotations

import copy
from dataclasses import replace

import pytest
from equiped_harness.agents.coordinator.batch_engine import (
    CONTRACT,
    validate_batch_bundle,
)
from equiped_harness.agents.coordinator.batch_findings import (
    ASSESSMENT_IDS,
    ASSESSMENT_KEY,
    ORGANIZATION_IDS,
    ORGANIZATION_KEY,
)
from historical_fixture import load_historical_fixture


def _v5_result():
    snapshot, result = load_historical_fixture(4)
    metadata = copy.deepcopy(result.metadata)
    bundle = metadata["current_bundle"]
    bundle["contract"] = CONTRACT
    bundle["narrative_units"] = {
        **{code: ORGANIZATION_KEY for code in ORGANIZATION_IDS},
        **{code: ASSESSMENT_KEY for code in ASSESSMENT_IDS},
        "summary": ASSESSMENT_KEY,
    }

    source_responses = metadata["group_responses"]
    metadata["group_responses"][ORGANIZATION_KEY] = {
        "results": [
            source_responses[f"finding-{code}"]["results"][0]
            for code in ORGANIZATION_IDS
        ]
    }
    metadata["group_responses"][ASSESSMENT_KEY] = {
        "results": [
            source_responses[f"finding-{code}"]["results"][0] for code in ASSESSMENT_IDS
        ],
        "summary": source_responses["finding-summary"]["results"][0]["summary"],
    }
    metadata["envelope_status"][ORGANIZATION_KEY] = "ok"
    metadata["envelope_status"][ASSESSMENT_KEY] = "ok"
    metadata["execution_contract"] = CONTRACT
    scores = tuple(
        replace(score, evidence=tuple(score.evidence), chunk_ids=tuple(score.chunk_ids))
        for score in result.criterion_scores
    )
    saved = replace(result, metadata=metadata, criterion_scores=scores)
    metadata["group_responses"]["__current_bundle__"] = bundle
    return snapshot, saved


def _tampered(result, mutate):
    metadata = copy.deepcopy(result.metadata)
    scores = result.criterion_scores
    mutate(metadata, scores)
    metadata["group_responses"]["__current_bundle__"] = metadata["current_bundle"]
    return replace(result, metadata=metadata)


def test_v5_integrity_rejects_missing_criterion_definition():
    snapshot, result = _v5_result()

    def mutate(metadata, _scores):
        metadata["current_bundle"]["criterion_definitions"].pop()

    with pytest.raises((ValueError, TypeError)):
        validate_batch_bundle(_tampered(result, mutate), snapshot)


def test_v5_integrity_rejects_forged_exact_quote():
    snapshot, result = _v5_result()

    def mutate(metadata, _scores):
        metadata["current_bundle"]["criteria"]["A-01"]["items"][0]["quote"] = (
            "A forged quotation absent from the source."
        )

    with pytest.raises((ValueError, TypeError)):
        validate_batch_bundle(_tampered(result, mutate), snapshot)


@pytest.mark.parametrize("field", ["coverage", "objective_rows"])
def test_v5_integrity_rejects_omitted_packet_coverage_or_objectives(field):
    snapshot, result = _v5_result()

    def mutate(metadata, _scores):
        bundle = metadata["current_bundle"]
        if field == "coverage":
            bundle["source_retrieval"]["coverage"] = {}
        else:
            bundle["objective"]["rows"].pop()

    with pytest.raises((ValueError, TypeError)):
        validate_batch_bundle(_tampered(result, mutate), snapshot)


def test_v5_integrity_rejects_narrative_text_changed_after_capture():
    snapshot, result = _v5_result()
    scores = tuple(
        replace(score, justification=score.justification + " Altered after capture.")
        if score.criterion_id == "OP-01"
        else score
        for score in result.criterion_scores
    )
    with pytest.raises((ValueError, TypeError)):
        validate_batch_bundle(replace(result, criterion_scores=scores), snapshot)


def test_v5_integrity_allows_server_chunk_id_augmentation():
    snapshot, result = _v5_result()
    scores = tuple(
        replace(
            score,
            chunk_ids=tuple(dict.fromkeys((*score.chunk_ids, "server-chunk"))),
        )
        if score.criterion_id == "OP-01"
        else score
        for score in result.criterion_scores
    )
    validate_batch_bundle(replace(result, criterion_scores=scores), snapshot)
