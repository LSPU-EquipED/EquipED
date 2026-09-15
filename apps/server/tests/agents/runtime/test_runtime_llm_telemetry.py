import pytest
from server.core.llm import CompletionResult
from server.modules.agents.exceptions import AgentLLMError
from server.modules.agents.provenance import sanitize_provenance
from server.modules.agents.runtime import llm


class TypedClient:
    model = "requested-model"

    def __init__(self, results):
        self.results = iter(results)

    def generate_result(
        self, prompt, *, temperature, max_new_tokens, deadline, response_contract
    ):
        return next(self.results)


def test_runtime_aggregates_typed_multi_call_usage_and_cap_hits():
    client = TypedClient(
        [
            CompletionResult(
                "one", "served-model", 11, 7, 18, "stop", 0.25, attempts=2
            ),
            CompletionResult("two", "served-model", 13, 5, 18, "stop", 0.5, attempts=3),
        ]
    )
    runtime = llm.RunLLMClient(client, "sme")

    assert runtime.generate("p1", temperature=0, max_new_tokens=10) == "one"
    assert runtime.generate("p2", temperature=0, max_new_tokens=10) == "two"
    assert runtime.actual_model == "served-model"
    assert runtime.telemetry["call_count"] == 2
    assert runtime.telemetry["attempt_count"] == 5
    assert runtime.telemetry["cap_hit_count"] == 0
    assert runtime.telemetry["prompt_tokens"] == 24
    assert runtime.telemetry["completion_tokens"] == 12
    assert runtime.telemetry["total_tokens"] == 36
    assert runtime.telemetry["usage_available"] is True
    assert runtime.telemetry["wall_seconds"] == 0.75


def test_runtime_marks_usage_unavailable_for_legacy_string_client():
    class LegacyClient:
        model = "legacy"

        def generate(self, prompt, *, temperature, max_new_tokens):
            return "text"

    runtime = llm.RunLLMClient(LegacyClient(), "itso")
    assert runtime.generate("p", temperature=0, max_new_tokens=1) == "text"
    assert runtime.telemetry["usage_available"] is False
    assert runtime.telemetry["prompt_tokens"] == 0
    assert runtime.telemetry["completion_tokens"] == 0
    assert runtime.telemetry["total_tokens"] == 0


def test_no_implicit_fallback_sequence(monkeypatch):
    class FailureClient:
        model = "primary"

        def generate(self, prompt, *, temperature, max_new_tokens):
            raise RuntimeError("provider unavailable")

    def unexpected_fallback():
        raise AssertionError("global fallback must not be consulted")

    monkeypatch.setattr(llm, "get_llm_client", unexpected_fallback)
    runtime = llm.RunLLMClient(FailureClient(), "gad")
    with pytest.raises(AgentLLMError) as exc_info:
        runtime.generate("p", temperature=0, max_new_tokens=1)
    assert str(exc_info.value).startswith("LLM call failed for gad (reference: ")
    assert runtime.telemetry["call_count"] == 1
    assert runtime.fallback_occurred is False
    assert runtime.actual_model == "primary"


def test_runtime_telemetry_is_bounded_and_provenance_safe():
    result = CompletionResult(
        "ok",
        "served",
        99_999_999,
        99_999_999,
        99_999_999,
        "length",
        99_999,
        attempts=99_999,
    )
    runtime = llm.RunLLMClient(TypedClient([result]), "sme")
    with pytest.raises(AgentLLMError):
        runtime.generate("p", temperature=0, max_new_tokens=1)

    assert runtime.telemetry["attempt_count"] == 32
    assert runtime.telemetry["prompt_tokens"] == 10_000_000
    assert runtime.telemetry["wall_seconds"] == 3600
    safe = sanitize_provenance(
        {
            "llm_attempts": runtime.telemetry["attempt_count"],
            "llm_served_model": "served-" + "x" * 500,
            "raw_prompt": "do not persist this raw prompt",
            "api_key": "secret-value",
        }
    )
    assert safe == {"llm_attempts": 32, "llm_served_model": "served-" + "x" * 193}
