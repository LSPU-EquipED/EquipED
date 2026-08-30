"""Telemetry and provenance contract tests for SME snapshot adapter."""

from __future__ import annotations

import json
import uuid

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.exceptions import AgentLLMError
from server.modules.agents.provenance import sanitize_provenance
from server.modules.agents.runtime.llm import RunLLMClient
from server.modules.agents.sme.agent import SME
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
)
from server.modules.rubrics.snapshot_contracts import build_evaluation_form_snapshot

_CHUNK_INFOS = [{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM"}]
_SOURCE = "Canonical SLM text for telemetry tests."


def _make_snapshot(eval_id: uuid.UUID):
    c1 = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="OP-02",
        title="Interactive Elements",
        description="Desc",
        display_order=0,
        strategy_config=CountBandConfig(
            mode="minimum_count", threshold_4=3, threshold_3=2, threshold_2=1
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="sme",
        adapter_key="sme",
        adapter_version=1,
        version_number=1,
        name="Telemetry Form",
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="D1",
                title="Domain 1",
                display_order=0,
                criteria=(c1,),
            ),
        ),
    )
    return build_evaluation_form_snapshot(eval_id, form)


class TypedSMEFake:
    model = "telemetry-model"

    def __init__(self, results: list[CompletionResult]) -> None:
        self.results = iter(results)
        self.calls = 0

    def generate_result(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None = None,
        response_contract: object = None,
    ) -> CompletionResult:
        self.calls += 1
        return next(self.results)


def test_healthy_run_records_telemetry_and_provenance():
    eval_id = uuid.uuid4()
    snap = _make_snapshot(eval_id)
    payload = json.dumps(
        {
            "summary": "ok",
            "criterion_measurements": [
                {
                    "criterion_id": "OP-02",
                    "criterion_title": "Interactive Elements",
                    "instances": [{"excerpt": "Canonical SLM text"}],
                }
            ],
        }
    )
    fake = TypedSMEFake(
        [CompletionResult(payload, "telemetry-model", 30, 60, 90, "stop", attempts=1)]
    )
    result = SME(llm_client=fake).run(
        evaluation_id=eval_id,
        document_id=uuid.uuid4(),
        form_snapshot=snap,
        chunk_infos=_CHUNK_INFOS,
        canonical_source_text=_SOURCE,
    )

    assert result.provenance == {
        "requested_model": "telemetry-model",
        "actual_model": "telemetry-model",
        "fallback_occurred": False,
        "repair_occurred": False,
        "logical_calls": 1,
        "physical_attempts": 1,
        "input_tokens": 30,
        "output_tokens": 60,
        "truncation_count": 0,
        "cap_hit_count": 0,
        "grouped_calls": 1,
        "provider_seconds_ms": 0,
        "trim_count": 0,
    }


def test_amplified_run_reports_fallback_and_cap():
    client = TypedSMEFake(
        [
            CompletionResult("{}", "telemetry-model", 10, 20, 30, "stop", attempts=2),
            CompletionResult("{}", "telemetry-model", 10, 20, 30, "length", attempts=2),
        ]
    )
    runtime = RunLLMClient(client, "sme")
    runtime.generate("grouped", temperature=0, max_new_tokens=10)
    with pytest.raises(AgentLLMError):
        runtime.generate("fallback", temperature=0, max_new_tokens=10)
    safe = sanitize_provenance(
        {
            "logical_calls": runtime.telemetry["call_count"],
            "physical_attempts": runtime.telemetry["attempt_count"],
            "input_tokens": runtime.telemetry["prompt_tokens"],
            "output_tokens": runtime.telemetry["completion_tokens"],
            "truncation_count": runtime.telemetry["cap_hit_count"],
            "cap_hit_count": runtime.telemetry["cap_hit_count"],
            "criterion_fallback_calls": 1,
        }
    )
    assert safe == {
        "logical_calls": 2,
        "physical_attempts": 4,
        "input_tokens": 20,
        "output_tokens": 40,
        "truncation_count": 1,
        "cap_hit_count": 1,
        "criterion_fallback_calls": 1,
    }


def test_sanitize_preserves_telemetry_and_drops_secret_prompt_response_markers():
    safe = sanitize_provenance(
        {
            "logical_calls": 6,
            "physical_attempts": 8,
            "input_tokens": 70,
            "output_tokens": 140,
            "truncation_count": 1,
            "cap_hit_count": 1,
            "criterion_fallback_calls": 1,
            "secret_marker": "secret",
            "prompt_marker": "prompt",
            "response_marker": "response",
        }
    )
    assert safe == {
        "logical_calls": 6,
        "physical_attempts": 8,
        "input_tokens": 70,
        "output_tokens": 140,
        "truncation_count": 1,
        "cap_hit_count": 1,
        "criterion_fallback_calls": 1,
    }


@pytest.mark.parametrize("value", [True, -1, 10_000_001])
def test_sanitize_rejects_invalid_telemetry_values(value):
    assert sanitize_provenance({"logical_calls": value}) is None
