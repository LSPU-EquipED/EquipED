"""Tests for SME snapshot envelope scoring."""

from __future__ import annotations

import json
import uuid

from server.core.llm import CompletionResult
from server.modules.agents.sme.agent import SME
from server.modules.agents.runtime.prompts import AgentPrompt
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    RatioBandConfig,
)
from server.modules.rubrics.snapshot_contracts import build_evaluation_form_snapshot

_CHUNK_INFOS = [{"chunk_id": "c1", "page_number": 1, "text": "x"}]
_CANONICAL = "clean SLM text with genuine interactive activity and tasks. " * 10


def _make_criterion(
    code: str, title: str, config: object, order: int = 0
) -> CriterionDefinition:
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=title,
        description=f"Description for {title}",
        display_order=order,
        strategy_config=config,
    )


def _make_snapshot(eval_id: uuid.UUID):
    d1 = (
        _make_criterion(
            "OP-01",
            "Topic Coherence",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            0,
        ),
    )
    d2 = (
        _make_criterion(
            "OP-02",
            "Interactive Elements",
            CountBandConfig(
                mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
            ),
            0,
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        version_number=1,
        name="Test Form",
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="D1",
                title="Domain 1",
                display_order=0,
                criteria=d1,
            ),
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="D2",
                title="Domain 2",
                display_order=1,
                criteria=d2,
            ),
        ),
    )
    return build_evaluation_form_snapshot(eval_id, form)


class MockLLM:
    def __init__(self, payloads: list[str]) -> None:
        self.payloads = list(payloads)
        self.prompts: list = []

    def generate_result(self, prompt, **kwargs: object) -> CompletionResult:
        self.prompts.append(prompt)
        return CompletionResult(
            content=self.payloads.pop(0),
            served_model="test-model",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            finish_reason="stop",
            attempts=1,
        )


def test_sme_run_scores_all_criteria_via_envelopes():
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id)
    payloads = [
        json.dumps(
            {
                "summary": "d1 ok",
                "criterion_measurements": [
                    {
                        "criterion_id": "OP-01",
                        "criterion_title": "Topic Coherence",
                        "total_units": [
                            {"unit_id": "u1", "evidence": "clean SLM text"}
                        ],
                        "qualifying_unit_ids": ["u1"],
                        "has_measurable_content": True,
                    }
                ],
            }
        ),
        json.dumps(
            {
                "summary": "d2 ok",
                "criterion_measurements": [
                    {
                        "criterion_id": "OP-02",
                        "criterion_title": "Interactive Elements",
                        "instances": [
                            {"excerpt": "genuine interactive activity"},
                            {"excerpt": "clean SLM text"},
                        ],
                    }
                ],
            }
        ),
    ]

    client = MockLLM(payloads)
    result = SME(llm_client=client).run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=_CHUNK_INFOS,
        canonical_source_text=_CANONICAL,
    )

    assert result.success is True
    assert len(result.criterion_scores) == 2
    assert result.criterion_scores[0].score == 4
    assert result.criterion_scores[1].score == 3
    assert set(result.metadata["group_prompts"]) == {"envelope_0", "envelope_1"}
    assert set(result.metadata["group_responses"]) == {"envelope_0", "envelope_1"}


def test_group_prompts_are_the_exact_prompts_sent():
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id)
    payloads = [
        json.dumps(
            {
                "summary": "d1 ok",
                "criterion_measurements": [
                    {
                        "criterion_id": "OP-01",
                        "criterion_title": "Topic Coherence",
                        "total_units": [
                            {"unit_id": "u1", "evidence": "clean SLM text"}
                        ],
                        "qualifying_unit_ids": ["u1"],
                        "has_measurable_content": True,
                    }
                ],
            }
        ),
        json.dumps(
            {
                "summary": "d2 ok",
                "criterion_measurements": [
                    {
                        "criterion_id": "OP-02",
                        "criterion_title": "Interactive Elements",
                        "instances": [{"excerpt": "clean SLM text"}],
                    }
                ],
            }
        ),
    ]
    client = MockLLM(payloads)
    result = SME(llm_client=client).run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=_CHUNK_INFOS,
        canonical_source_text=_CANONICAL,
    )

    assert set(result.metadata["group_prompts"].values()) == {
        prompt.render_flat() for prompt in client.prompts
    }
    assert all(isinstance(prompt, AgentPrompt) for prompt in client.prompts)
    assert all(prompt.messages[0].role == "system" for prompt in client.prompts)
    assert all(prompt.messages[1].role == "user" for prompt in client.prompts)
    assert all(
        "=== UNTRUSTED SOURCE TEXT ===" in prompt.user_context
        for prompt in client.prompts
    )
