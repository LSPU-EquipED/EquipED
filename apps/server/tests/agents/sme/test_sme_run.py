"""Tests for SME.run() driven by snapshot envelopes."""

from __future__ import annotations

import json
import uuid

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.sme.agent import SME
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    RatioBandConfig,
)
from server.modules.rubrics.snapshot_contracts import build_evaluation_form_snapshot

_CHUNK_INFOS = [{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}]
_SOURCE = (
    "Unit 1 Topic A. Unit 2 Topic B. Interactive practice task. "
    "Accurate section details."
)


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
        _make_criterion(
            "OP-02",
            "Interactive Elements",
            CountBandConfig(
                mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
            ),
            1,
        ),
    )
    d2 = (
        _make_criterion(
            "A-01",
            "Higher-Order Thinking",
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80.0,
                threshold_3=50.0,
                threshold_2=20.0,
            ),
            0,
        ),
        _make_criterion(
            "A-02",
            "Varied Assessments",
            CountBandConfig(
                mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
            ),
            1,
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        version_number=1,
        name="Test SME Form",
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="ID_ORG",
                title="Design",
                display_order=0,
                criteria=d1,
            ),
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="ASSESS",
                title="Assessments",
                display_order=1,
                criteria=d2,
            ),
        ),
    )
    return build_evaluation_form_snapshot(eval_id, form)


class MockLLM:
    def __init__(
        self, payloads: list[str | Exception], model: str = "mock-sme-model"
    ) -> None:
        self.payloads = list(payloads)
        self.model = model
        self.call_count = 0

    def generate_result(self, prompt: str, **kwargs: object) -> CompletionResult:
        self.call_count += 1
        if not self.payloads:
            raise RuntimeError("No more payloads")
        item = self.payloads.pop(0)
        if isinstance(item, Exception):
            raise item
        return CompletionResult(
            content=item,
            served_model=self.model,
            prompt_tokens=20,
            completion_tokens=40,
            total_tokens=60,
            finish_reason="stop",
            attempts=1,
        )


def _valid_payload_for_d1() -> str:
    return json.dumps(
        {
            "summary": "Design domain ok",
            "criterion_measurements": [
                {
                    "criterion_id": "OP-01",
                    "criterion_title": "Topic Coherence",
                    "total_units": [{"unit_id": "u1", "evidence": "Unit 1 Topic A."}],
                    "qualifying_unit_ids": ["u1"],
                    "has_measurable_content": True,
                },
                {
                    "criterion_id": "OP-02",
                    "criterion_title": "Interactive Elements",
                    "instances": [{"excerpt": "Interactive practice task."}],
                },
            ],
        }
    )


def _valid_payload_for_d2() -> str:
    return json.dumps(
        {
            "summary": "Assessment domain ok",
            "criterion_measurements": [
                {
                    "criterion_id": "A-01",
                    "criterion_title": "Higher-Order Thinking",
                    "total_units": [
                        {"unit_id": "u1", "evidence": "Accurate section details."}
                    ],
                    "qualifying_unit_ids": ["u1"],
                    "has_measurable_content": True,
                },
                {
                    "criterion_id": "A-02",
                    "criterion_title": "Varied Assessments",
                    "instances": [{"excerpt": "Interactive practice task."}],
                },
            ],
        }
    )


def test_full_success_scores_all_criteria() -> None:
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id)
    client = MockLLM([_valid_payload_for_d1(), _valid_payload_for_d2()])
    agent = SME(llm_client=client)

    result = agent.run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=_CHUNK_INFOS,
        canonical_source_text=_SOURCE,
    )

    assert result.success is True
    assert len(result.criterion_scores) == 4
    assert result.summary != ""
    assert "strongest area" in result.summary
    assert client.call_count == 2


def test_repair_on_validation_failure() -> None:
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id)
    # First call invalid JSON, repair valid JSON, second envelope valid
    client = MockLLM(["bad json", _valid_payload_for_d1(), _valid_payload_for_d2()])
    agent = SME(llm_client=client)

    result = agent.run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=_CHUNK_INFOS,
        canonical_source_text=_SOURCE,
    )

    assert result.success is True
    assert client.call_count == 3
    assert result.provenance["repair_occurred"] is True


def test_repair_failure_raises() -> None:
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id)
    # Both primary and repair fail on envelope 0
    client = MockLLM(["bad json 1", "bad json 2"])
    agent = SME(llm_client=client)

    with pytest.raises(AgentExecutionError, match="invalid JSON"):
        agent.run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            form_snapshot=snap,
            chunk_infos=_CHUNK_INFOS,
            canonical_source_text=_SOURCE,
        )


def test_model_name_uses_client_model() -> None:
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id)
    client = MockLLM(
        [_valid_payload_for_d1(), _valid_payload_for_d2()], model="custom-sme-model"
    )
    agent = SME(llm_client=client)

    result = agent.run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=_CHUNK_INFOS,
        canonical_source_text=_SOURCE,
    )

    assert result.model_name == "custom-sme-model"


def test_raises_when_no_chunk_infos() -> None:
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id)
    agent = SME(llm_client=MockLLM([]))

    with pytest.raises(AgentExecutionError, match="document chunks"):
        agent.run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            form_snapshot=snap,
            chunk_infos=[],
            canonical_source_text=_SOURCE,
        )


def test_raises_when_no_text_available() -> None:
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id)
    agent = SME(llm_client=MockLLM([]))

    with pytest.raises(AgentExecutionError, match="canonical source text"):
        agent.run(
            evaluation_id=eval_id,
            document_id=uuid.uuid4(),
            form_snapshot=snap,
            chunk_infos=_CHUNK_INFOS,
            canonical_source_text="",
        )
