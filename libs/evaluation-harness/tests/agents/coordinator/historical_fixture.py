"""Readers for frozen pre-v5 Coordinator integrity fixtures."""

from __future__ import annotations

import gzip
import json
from dataclasses import fields
from pathlib import Path
from uuid import UUID

from equiped_harness.agents.coordinator.contracts import CoordinatorAlignmentAdvisory
from equiped_harness.contracts.results import (
    AgentEvaluationResult,
    CriterionScore,
)
from equiped_harness.contracts.snapshots import EvaluationFormSnapshotDTO


def load_historical_fixture(
    version: int,
) -> tuple[EvaluationFormSnapshotDTO, AgentEvaluationResult]:
    """Load a frozen v3/v4 fixture without invoking a legacy runtime."""
    path = (
        Path(__file__).with_name("fixtures") / f"coordinator_current_v{version}.json.gz"
    )
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)

    snapshot = EvaluationFormSnapshotDTO.model_validate(payload["snapshot"])
    raw = dict(payload["result"])
    raw.pop("generations", None)
    metadata = dict(raw.get("metadata") or {})
    responses = dict(metadata.get("group_responses") or {})
    bundle = responses.pop("__current_bundle__", None)
    if bundle is None:
        raise ValueError("historical fixture is missing its current bundle")
    metadata["group_responses"] = responses
    metadata["current_bundle"] = bundle
    raw["metadata"] = metadata

    raw["evaluation_id"] = UUID(raw["evaluation_id"])
    raw["document_id"] = UUID(raw["document_id"])
    if raw.get("prompt_version_id"):
        raw["prompt_version_id"] = UUID(raw["prompt_version_id"])
    raw["criterion_scores"] = tuple(
        CriterionScore(
            **{
                **row,
                "evidence": tuple(row.get("evidence", [])),
                "chunk_ids": tuple(row.get("chunk_ids", [])),
            }
        )
        for row in raw.get("criterion_scores", [])
    )
    advisory = raw.get("advisory_outputs")
    if (
        isinstance(advisory, dict)
        and advisory.get("contract") == "coordinator_alignment.v1"
    ):
        raw["advisory_outputs"] = CoordinatorAlignmentAdvisory.from_dict(advisory)
    allowed = {field.name for field in fields(AgentEvaluationResult)}
    result = AgentEvaluationResult(
        **{key: value for key, value in raw.items() if key in allowed}
    )
    return snapshot, result
