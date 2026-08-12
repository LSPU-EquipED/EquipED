import pytest
from server.modules.agents.exceptions import AgentLLMError
from server.modules.agents.runtime import llm


class Client:
    model = "primary"

    def generate_result(
        self,
        prompt,
        *,
        temperature,
        max_new_tokens,
        deadline,
        response_contract,
    ):
        raise RuntimeError("HTTP 503")


def test_adapter_primary_failure_is_safe_and_does_not_use_global_fallback():
    primary = Client()
    adapter = llm.RunLLMClient(primary, "itso")

    with pytest.raises(AgentLLMError) as exc_info:
        adapter.generate("p", temperature=0.7, max_new_tokens=123)

    assert str(exc_info.value).startswith("LLM call failed for itso")
    assert adapter.requested_model == "primary"
    assert adapter.actual_model == "primary"
    assert adapter.fallback_occurred is False


def test_adapter_typed_served_model_and_multi_call_telemetry():
    from server.core.llm import CompletionResult

    class Typed:
        model = "requested"

        def generate_result(self, *args, **kwargs):
            return CompletionResult("{}", "served", 2, 3, 5, "length", 0.1, attempts=2)

    adapter = llm.RunLLMClient(Typed(), "itso")
    with pytest.raises(AgentLLMError):
        adapter.generate("p", temperature=0, max_new_tokens=1)
    with pytest.raises(AgentLLMError):
        adapter.generate("p", temperature=0, max_new_tokens=1)
    assert adapter.actual_model == "served"
    assert adapter.fallback_occurred is False
    assert adapter.telemetry["call_count"] == 2
    assert adapter.telemetry["cap_hit_count"] == 2


def test_adapter_legacy_string_client_has_unavailable_usage():
    class ModelLessClient:
        def generate(self, prompt, *, temperature, max_new_tokens):
            return "unused"

    adapter = llm.RunLLMClient(ModelLessClient(), "itso", requested_model="requested")
    assert adapter.requested_model == "requested"
    assert adapter.actual_model == "requested"
    assert adapter.model == "requested"
    adapter.generate("p", temperature=0, max_new_tokens=1)
    assert adapter.actual_model == "requested"
    assert adapter.model == "requested"
    assert adapter.fallback_occurred is False
    assert adapter.telemetry["usage_available"] is False
