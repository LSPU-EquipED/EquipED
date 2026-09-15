"""Tests for GAD snapshot adapter, dynamic rules, and deterministic scoring."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from server.core.llm import CompletionResult, ResponseContract
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.gad.agent import GAD
from server.modules.agents.gad.envelope import parse_combined_response
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)
from server.modules.rubrics.snapshot_contracts import (
    build_evaluation_form_snapshot,
)
from server.tests.agents.gad.conftest import (
    make_gad_snapshot,
)

_CHUNKS = [
    {
        "chunk_id": "chunk_1",
        "page_number": 1,
        "text": (
            "Section 1: The male doctor and female nurse treated the patients. "
            "Section 2: Women are inherently too emotional for leadership. "
            "Section 3: Men are always rational decision makers."
        ),
    }
]


class _MockLLM:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []
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
        del temperature, max_new_tokens, deadline, response_contract
        self.prompts.append(prompt)
        if not self.responses:
            raise RuntimeError("No more mock responses")
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return CompletionResult(
            content=resp,
            served_model=self.model,
            finish_reason="stop",
        )


def _make_criterion(
    code: str,
    title: str,
    strategy_config: Any,
    scoring_rule: str | None = None,
    display_order: int = 0,
) -> CriterionDefinition:
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=title,
        description=f"Description for {title}",
        scoring_rule=scoring_rule,
        display_order=display_order,
        strategy_config=strategy_config,
    )


def test_gad_revision_1_parity() -> None:
    """Revision 1 evaluation scores 5 criteria correctly using snapshot configs."""
    eval_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    snapshot = make_gad_snapshot(evaluation_id=eval_id)

    response_payload = {
        "gad-01": {
            "instance_count": 2,
            "instances": [
                {
                    "excerpt": "Women are inherently too emotional for leadership.",
                    "chunk_id": "chunk_1",
                    "explanation": "Stereotype regarding women",
                },
                {
                    "excerpt": "Men are always rational decision makers.",
                    "chunk_id": "chunk_1",
                    "explanation": "Stereotype regarding men",
                },
            ],
            "summary": "Found 2 gender stereotype instances.",
        },
        "gad-02": {
            "female_count": 1,
            "male_count": 1,
            "summary": "Balanced representation (1 female nurse, 1 male doctor).",
        },
        "gad-03": {
            "instance_count": 0,
            "instances": [],
            "summary": "Equal respect maintained.",
        },
        "gad-04": {
            "instance_count": 0,
            "instances": [],
            "summary": "Needs and life experiences reflected equally.",
        },
        "gad-05": {
            "instance_count": 0,
            "instances": [],
            "summary": "Promotes peace and equality.",
        },
    }

    mock_llm = _MockLLM([json.dumps(response_payload)])
    gad = GAD(llm_client=mock_llm)

    result: AgentEvaluationResult = gad.run(
        evaluation_id=eval_id,
        document_id=doc_id,
        chunk_infos=_CHUNKS,
        form_snapshot=snapshot,
    )

    assert result.success is True
    assert len(result.criterion_scores) == 5
    scores_by_id = {s.criterion_id: s for s in result.criterion_scores}

    # GAD-01: count_band maximum_count 0->4, 1->3, 3->2; count is 2 => score 2
    assert scores_by_id["GAD-01"].score == 2
    assert len(scores_by_id["GAD-01"].evidence) == 2

    # GAD-02: ratio_band absolute_difference 2.0->4, 5.0->3, 10.0->2
    # diff is |1-1|=0 <= 2 => score 4
    assert scores_by_id["GAD-02"].score == 4

    # GAD-03, GAD-04, GAD-05: 0 instances => score 4
    assert scores_by_id["GAD-03"].score == 4
    assert scores_by_id["GAD-04"].score == 4
    assert scores_by_id["GAD-05"].score == 4

    # Subtotal: (2 + 4 + 4 + 4 + 4) / 5 = 3.6
    assert result.subtotal == pytest.approx(3.6)


def test_gad_dynamic_criteria_add_remove_reorder() -> None:
    """Snapshot with custom codes, additions, removals, and reordering works."""
    eval_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    custom_crit1 = _make_criterion(
        "CUSTOM-RATIO",
        "Gender Pronoun Balance",
        RatioBandConfig(
            strategy="ratio_band",
            mode="absolute_difference",
            threshold_4=1.0,
            threshold_3=3.0,
            threshold_2=6.0,
        ),
        display_order=0,
    )
    custom_crit2 = _make_criterion(
        "CUSTOM-BIAS",
        "Explicit Bias Count",
        CountBandConfig(
            strategy="count_band",
            mode="maximum_count",
            threshold_4=0,
            threshold_3=1,
            threshold_2=2,
        ),
        display_order=1,
    )

    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="Custom GAD Form",
        version_number=2,
        adapter_key="gad",
        adapter_version=1,
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="CUSTOM_GAD",
                title="Custom GAD Domain",
                display_order=0,
                criteria=(custom_crit1, custom_crit2),
            ),
        ),
    )
    snapshot = build_evaluation_form_snapshot(eval_id, form)

    response_payload = {
        "custom-ratio": {
            "female_count": 5,
            "male_count": 2,
            "summary": "Female 5, male 2, diff 3.",
        },
        "custom-bias": {
            "instance_count": 1,
            "instances": [
                {
                    "excerpt": "Women are inherently too emotional for leadership.",
                    "chunk_id": "chunk_1",
                    "explanation": "Explicit bias statement",
                }
            ],
            "summary": "Found 1 bias instance.",
        },
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
    assert len(result.criterion_scores) == 2
    assert result.criterion_scores[0].criterion_id == "CUSTOM-RATIO"
    # diff=3, threshold_3=3.0 => score 3
    assert result.criterion_scores[0].score == 3
    assert result.criterion_scores[1].criterion_id == "CUSTOM-BIAS"
    # count=1, threshold_3=1 => score 3
    assert result.criterion_scores[1].score == 3
    assert result.subtotal == pytest.approx(3.0)


def test_gad_rejects_score_fields_in_llm_response() -> None:
    """Extraction response containing numeric score fields is rejected."""
    snapshot = make_gad_snapshot()
    raw = json.dumps(
        {
            "gad-01": {
                "instance_count": 0,
                "instances": [],
                "summary": "clean",
                "score": 4,  # forbidden score field
            },
            "gad-02": {"female_count": 1, "male_count": 1, "summary": "ok"},
            "gad-03": {"instance_count": 0, "instances": [], "summary": "ok"},
            "gad-04": {"instance_count": 0, "instances": [], "summary": "ok"},
            "gad-05": {"instance_count": 0, "instances": [], "summary": "ok"},
        }
    )
    with pytest.raises(AgentExecutionError, match="prohibited numeric-score field"):
        parse_combined_response(raw, form_snapshot=snapshot)


def test_gad_whole_envelope_repair_on_malformed_response() -> None:
    """Malformed initial response triggers bounded whole-envelope repair."""
    eval_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    snapshot = make_gad_snapshot(evaluation_id=eval_id)

    malformed_response = "{ invalid json..."
    valid_repair_response = json.dumps(
        {
            "gad-01": {
                "instance_count": 0,
                "instances": [],
                "summary": "No stereotypes.",
            },
            "gad-02": {
                "female_count": 2,
                "male_count": 2,
                "summary": "Equal count.",
            },
            "gad-03": {
                "instance_count": 0,
                "instances": [],
                "summary": "Equal respect.",
            },
            "gad-04": {
                "instance_count": 0,
                "instances": [],
                "summary": "Equal experiences.",
            },
            "gad-05": {
                "instance_count": 0,
                "instances": [],
                "summary": "Peace and equality.",
            },
        }
    )

    mock_llm = _MockLLM([malformed_response, valid_repair_response])
    gad = GAD(llm_client=mock_llm)

    result = gad.run(
        evaluation_id=eval_id,
        document_id=doc_id,
        chunk_infos=_CHUNKS,
        form_snapshot=snapshot,
    )

    assert result.success is True
    assert len(result.criterion_scores) == 5
    assert result.provenance is not None
    assert result.provenance.get("repair_occurred") is True


def test_gad_unrecoverable_failure_fails_closed() -> None:
    """Unrecoverable malformed response returns failure without broad swallowing."""
    eval_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    snapshot = make_gad_snapshot(evaluation_id=eval_id)

    mock_llm = _MockLLM(["{ bad json 1", "{ bad json 2"])
    gad = GAD(llm_client=mock_llm)

    result = gad.run(
        evaluation_id=eval_id,
        document_id=doc_id,
        chunk_infos=_CHUNKS,
        form_snapshot=snapshot,
    )

    assert result.success is False
    assert result.subtotal == 0.0
    assert result.criterion_scores == ()
    assert "GADExecutionFailure" in (result.error_message or "")


def test_gad_rejects_unsupported_strategy_configuration() -> None:
    """Snapshot containing unsupported strategy (e.g. LLM guidance) is refused."""
    eval_id = uuid.uuid4()
    unsupported_crit = _make_criterion(
        "GAD-BAD",
        "Bad Strategy",
        LlmRubricGuidanceConfig(
            strategy="llm_rubric_guidance",
            guidance="Score this directly with LLM",
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="Invalid GAD Form",
        version_number=1,
        adapter_key="gad",
        adapter_version=1,
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="GAD",
                title="GAD Domain",
                display_order=0,
                criteria=(unsupported_crit,),
            ),
        ),
    )
    snapshot = build_evaluation_form_snapshot(eval_id, form)

    gad = GAD()
    with pytest.raises(AgentExecutionError, match="Unsupported strategy config"):
        gad.run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNKS,
            form_snapshot=snapshot,
        )


def test_gad_rejects_duplicate_chunk_ids() -> None:
    """Duplicate chunk IDs in input fail closed."""
    eval_id = uuid.uuid4()
    snapshot = make_gad_snapshot(evaluation_id=eval_id)
    dup_chunks = [
        {"chunk_id": "c1", "text": "Text 1"},
        {"chunk_id": "c1", "text": "Text 2"},
    ]
    gad = GAD()
    with pytest.raises(AgentExecutionError, match="duplicate chunk_id"):
        gad.run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            chunk_infos=dup_chunks,
            form_snapshot=snapshot,
        )
