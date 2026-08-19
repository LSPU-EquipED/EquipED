from __future__ import annotations

import uuid

import pytest
from server.core.llm import CompletionResult
from server.modules.agents.provenance import sanitize_provenance
from server.modules.agents.runtime.llm import RunLLMClient
from server.modules.agents.sme.agent import SME
from server.modules.agents.sme.oracle import registry
from server.tests.agents.helpers import GroupScoringFakeClient, sme_group_payloads

_TELEMETRY_TITLES = {code: f"{code} title" for code in registry.REGISTERED_CODES}


class TypedSMEFake:
    """Replays canned completions in order; used for the raw-adapter cases."""

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


def _run(monkeypatch: pytest.MonkeyPatch, client: GroupScoringFakeClient):
    monkeypatch.setattr(
        "server.modules.agents.sme.pipeline.get_active_rubric_criteria",
        lambda agent_id, db=None: {
            code: f"{code} title" for code in registry.REGISTERED_CODES
        },
    )
    monkeypatch.setattr(
        "server.modules.agents.sme.pipeline.get_active_rubric_descriptions",
        lambda agent_id, db=None: {},
    )
    return SME(llm_client=client).run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM"}],
        context_text="SLM text",
        canonical_source_text="SLM text",
    )


def test_healthy_grouped_run_has_three_logical_calls_and_exact_totals(monkeypatch):
    client = GroupScoringFakeClient(
        sme_group_payloads(3, titles=_TELEMETRY_TITLES), model="telemetry-model"
    )
    result = _run(monkeypatch, client)

    assert result.provenance == {
        "requested_model": "telemetry-model",
        "actual_model": "telemetry-model",
        "fallback_occurred": False,
        "logical_calls": 3,
        "physical_attempts": 3,
        "input_tokens": 30,
        "output_tokens": 60,
        "truncation_count": 0,
        "cap_hit_count": 0,
        "criterion_fallback_calls": 0,
        "grouped_calls": 3,
        "fallback_calls": 0,
        "provider_seconds_ms": 0,
        "trim_count": 0,
    }


def test_amplified_run_reports_group_invalidity_fallback_and_cap(monkeypatch):
    from server.modules.agents.exceptions import AgentLLMError

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
