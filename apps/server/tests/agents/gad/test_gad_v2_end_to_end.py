"""End-to-end regression coverage for GAD.run() against a v2 (llm_rubric_
guidance) snapshot -- guards against the exact class of bug documented in
project memory gad-agent-py-manifest-bug: a manifest version bump landing
without agent.py's own validation gate being updated to match."""

from __future__ import annotations

import json
import uuid

from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.gad.agent import GAD
from server.tests.agents.gad.conftest import make_gad_snapshot, make_gad_snapshot_v2

_CHUNKS = [
    {
        "chunk_id": "chunk_1",
        "text": (
            "Section 1: The male doctor and female nurse treated the patients. "
            "Section 2: Women are inherently too emotional for leadership."
        ),
    }
]


class _MockLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.model = "mock-gad-model"

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None,
        response_contract: ResponseContract,
    ) -> CompletionResult:
        del prompt, temperature, max_new_tokens, deadline, response_contract
        return CompletionResult(
            content=self.responses.pop(0),
            served_model=self.model,
            finish_reason="stop",
        )


def test_gad_v2_snapshot_scores_end_to_end() -> None:
    eval_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    snapshot = make_gad_snapshot_v2(evaluation_id=eval_id)

    response_payload = {
        "gad-01": {
            "score": 2,
            "evidence": "Women are inherently too emotional for leadership.",
            "chunk_id": "chunk_1",
            "reasoning": "Direct gender stereotype statement.",
            "summary": "One clear stereotype found.",
        }
    }
    mock_llm = _MockLLM([json.dumps(response_payload)])
    gad = GAD(llm_client=mock_llm)

    result = gad.run(
        evaluation_id=eval_id,
        document_id=doc_id,
        chunk_infos=_CHUNKS,
        form_snapshot=snapshot,
    )

    assert result.success is True
    assert len(result.criterion_scores) == 1
    assert result.criterion_scores[0].criterion_id == "GAD-01"
    assert result.criterion_scores[0].score == 2
    assert result.subtotal == 2.0
    assert len(result.generations) == 1
    assert result.generations[0].response_contract_key == "gad_scores.v1"


def test_gad_v1_snapshot_still_scores_end_to_end_unchanged() -> None:
    """Regression guard: v1 (count/ratio) evaluations must keep working
    unmodified after v2 support and the manifest-driven gate land."""
    eval_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    snapshot = make_gad_snapshot(evaluation_id=eval_id)

    response_payload = {
        "gad-01": {"instance_count": 0, "instances": [], "summary": "None found."},
        "gad-02": {"female_count": 1, "male_count": 1, "summary": "Balanced."},
        "gad-03": {"instance_count": 0, "instances": [], "summary": "None found."},
        "gad-04": {"instance_count": 0, "instances": [], "summary": "None found."},
        "gad-05": {"instance_count": 0, "instances": [], "summary": "None found."},
    }
    mock_llm = _MockLLM([json.dumps(response_payload)])
    gad = GAD(llm_client=mock_llm)

    result = gad.run(
        evaluation_id=eval_id,
        document_id=doc_id,
        chunk_infos=_CHUNKS,
        form_snapshot=snapshot,
    )

    assert result.success is True
    assert len(result.criterion_scores) == 5
    assert result.subtotal == 4.0
    assert len(result.generations) == 1
    assert result.generations[0].response_contract_key == "gad_extraction.v1"


def test_gad_v2_ungrounded_evidence_degrades_to_advisory_end_to_end() -> None:
    """Regression guard for the grounding-fallback fix: evidence the model
    cites that cannot be found in any chunk must NOT fail the whole
    evaluation -- it degrades to an advisory flag and the run still
    completes with a score."""
    eval_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    snapshot = make_gad_snapshot_v2(evaluation_id=eval_id)

    response_payload = {
        "gad-01": {
            "score": 2,
            "evidence": "This exact sentence never appears in the document.",
            "chunk_id": "chunk_1",
            "reasoning": "Model claims a stereotype but misquoted it.",
            "summary": "One instance claimed.",
        }
    }
    mock_llm = _MockLLM([json.dumps(response_payload)])
    gad = GAD(llm_client=mock_llm)

    result = gad.run(
        evaluation_id=eval_id,
        document_id=doc_id,
        chunk_infos=_CHUNKS,
        form_snapshot=snapshot,
    )

    assert result.success is True
    assert len(result.criterion_scores) == 1
    assert result.criterion_scores[0].score == 2
    assert result.criterion_scores[0].evidence == ()
    assert result.advisory_outputs is not None
    assert result.advisory_outputs.ungrounded_criteria[0].criterion_id == "GAD-01"
