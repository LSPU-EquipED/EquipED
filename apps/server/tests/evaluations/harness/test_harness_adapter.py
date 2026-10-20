"""The backend adapter delegates transport policy without retries or identity loss."""

import pytest
from equiped_harness import CompletionResult, ResponseContract

from server.core.config import Settings
from server.core.exceptions import ConfigurationError
from server.core.llm import ResponseContract as CoreResponseContract
from server.modules.evaluations.harness_adapter import (
    HarnessModelClient,
    execution_config_from_settings,
    tool_config_from_settings,
)


class Client:
    model = "requested-model"

    def __init__(self, failure=None):
        self.calls = []
        self.failure = failure
        self.result = CompletionResult("{}", "served-model", attempts=3)

    def generate_result(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.failure is not None:
            raise self.failure
        return self.result


@pytest.mark.parametrize(
    "contract",
    [
        None,
        ResponseContract.json_object(),
        ResponseContract.json_schema(
            {"type": "object", "properties": {"items": {"type": "array"}}}
        ),
    ],
)
def test_adapter_translates_contract_and_delegates_once(contract):
    client = Client()
    adapter = HarnessModelClient(client)
    prompt = [{"role": "user", "content": "prepared-input"}]
    result = adapter.generate_result(
        prompt,
        temperature=0.3,
        max_new_tokens=57,
        deadline=123.5,
        response_contract=contract,
    )
    assert adapter.model == "requested-model"
    assert result is client.result
    assert result.served_model == "served-model" and result.attempts == 3
    assert len(client.calls) == 1
    sent_prompt, kwargs = client.calls[0]
    assert sent_prompt is prompt
    assert kwargs["temperature"] == 0.3 and kwargs["max_new_tokens"] == 57
    assert kwargs["deadline"] == 123.5
    translated = kwargs["response_contract"]
    if contract is None:
        assert translated is None
    else:
        assert isinstance(translated, CoreResponseContract)
        assert (translated.mode, translated.schema_name, translated.schema) == (
            contract.mode,
            contract.schema_name,
            contract.schema,
        )


def test_adapter_rejects_foreign_or_invalid_contract_before_transport():
    client = Client()
    adapter = HarnessModelClient(client)
    invalid = ResponseContract.json_object()
    object.__setattr__(invalid, "mode", "invalid")
    for contract in (object(), CoreResponseContract.json_object(), invalid):
        with pytest.raises(ConfigurationError):
            adapter.generate_result(
                "p", temperature=0, max_new_tokens=5, response_contract=contract
            )
    assert not client.calls


def test_adapter_does_not_retry_or_wrap_transport_failure():
    failure = RuntimeError("provider failure")
    client = Client(failure)
    with pytest.raises(RuntimeError) as caught:
        HarnessModelClient(client).generate_result(
            "p", temperature=0, max_new_tokens=5, deadline=12
        )
    assert caught.value is failure
    assert len(client.calls) == 1


def test_config_translation_does_not_tighten_backend_values():
    settings = Settings(
        llm_temperature=3.5,
        agent_max_chunks=10_000_001,
        agent_total_prompt_budget_chars=10_000_002,
    )
    config = execution_config_from_settings(settings)
    assert config.llm_temperature == 3.5
    assert config.agent_max_chunks == settings.agent_max_chunks
    assert (
        config.agent_total_prompt_budget_chars
        == settings.agent_total_prompt_budget_chars
    )


@pytest.mark.parametrize("value", [None, "false", False, 1])
def test_public_tool_authorization_fails_closed(value):
    settings = type("Settings", (), {"itso_verification_enabled": value})()

    config = tool_config_from_settings(settings)

    assert config.enabled is False


def test_public_tool_authorization_requires_explicit_true():
    assert tool_config_from_settings(object()).enabled is False
    settings = type("Settings", (), {"itso_verification_enabled": True})()
    assert tool_config_from_settings(settings).enabled is True
