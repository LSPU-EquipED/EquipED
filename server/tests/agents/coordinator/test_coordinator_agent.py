"""Tests for the rewritten Coordinator agent (10-criterion grouped scoring)."""

from __future__ import annotations

import json
import uuid

import pytest
from server.core.llm import get_llm_model_name
from server.modules.agents.coordinator.agent import Coordinator
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.runtime.llm import RunLLMClient
from server.tests.agents.helpers import SequencedFakeClient, make_coordinator_snapshot

TEN = (
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
)
_COUNT_CODES = {"OP-02", "OP-05", "A-02", "A-03", "A-04"}
CURRICULUM = "Unit 2 covers photosynthesis and cellular respiration."
SOURCE = "Objective: explain photosynthesis. " * 3 + "Answer key provided. " * 3


def _measurement(code: str, titles: dict[str, str]) -> dict:
    title = titles[code]
    if code == "A-05":
        return {
            "criterion_id": code,
            "criterion_title": title,
            "alignments": [
                {
                    "objective_text": "Objective: explain photosynthesis.",
                    "is_aligned": True,
                    "assessment_excerpt": "Unit 2 covers photosynthesis",
                    "reasoning": None,
                }
            ],
        }
    if code in _COUNT_CODES:
        return {
            "criterion_id": code,
            "criterion_title": title,
            "instances": [{"excerpt": "Answer key provided."}],
        }
    return {
        "criterion_id": code,
        "criterion_title": title,
        "total_units": [{"unit_id": "u1", "evidence": "Answer key provided."}],
        "qualifying_unit_ids": ["u1"],
        "has_measurable_content": True,
    }


def _envelope_response(codes: tuple[str, ...], titles: dict[str, str]) -> dict:
    return {
        "summary": "ok",
        "criterion_measurements": [_measurement(c, titles) for c in codes],
    }


def _client(responses: list) -> RunLLMClient:
    fake = SequencedFakeClient(responses)
    fake.model = get_llm_model_name()
    return RunLLMClient(fake, "coordinator", requested_model="test-model")


def _run(client: RunLLMClient, snap, **overrides):
    kwargs = dict(
        evaluation_id=snap.evaluation_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=[{"chunk_id": str(uuid.uuid4())}],
        canonical_source_text=SOURCE,
        curriculum_id=uuid.uuid4(),
        curriculum_context=CURRICULUM,
        llm_client=client,
    )
    kwargs.update(overrides)
    return Coordinator().run(**kwargs)


def test_run_scores_all_ten_criteria_in_snapshot_order():
    snap, titles = make_coordinator_snapshot()
    client = _client(
        [
            _envelope_response(TEN[:5], titles),
            _envelope_response(TEN[5:], titles),
        ]
    )
    result = _run(client, snap)

    assert result.success is True
    assert tuple(s.criterion_id for s in result.criterion_scores) == TEN
    assert result.subtotal == sum(s.score for s in result.criterion_scores) / 10
    assert result.summary
    assert result.metadata["group_prompts"].keys() == {"envelope_0", "envelope_1"}
    assert result.metadata["group_responses"]["envelope_1"]
    assert "_grounding_rejected_count" not in json.dumps(
        result.metadata["group_responses"]
    )
    assert result.provenance["grouped_calls"] == 2
    assert "grounding_rejected_count" in result.provenance


def test_run_without_curriculum_context_fails():
    snap, _ = make_coordinator_snapshot()
    with pytest.raises(AgentExecutionError):
        _run(_client([]), snap, curriculum_id=None, curriculum_context=None)


def test_run_envelope_double_failure_propagates():
    snap, _ = make_coordinator_snapshot()
    with pytest.raises(AgentExecutionError):
        _run(_client(["bad", "still bad"]), snap)
