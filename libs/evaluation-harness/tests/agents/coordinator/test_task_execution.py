"""Bounded Coordinator response repair behavior."""

import time

import pytest
from equiped_harness import CompletionResult, ExecutionConfig, execution_scope
from equiped_harness.agents.coordinator.task_execution import _call_task
from equiped_harness.exceptions import AgentExecutionError, AgentLLMError
from equiped_harness.runtime.llm import RunLLMClient
from equiped_harness.runtime.model import ResponseContract
from equiped_harness.runtime.prompts import AgentPrompt


class ScriptedClient:
    model = "offline-test"

    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def generate_result(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        output = next(self.outputs)
        if isinstance(output, BaseException):
            raise output
        return output


def result(content, *, finish_reason=None):
    return CompletionResult(content, "offline-test", finish_reason=finish_reason)


def call(client, *, response_budget=512, config=None):
    deadline = time.monotonic() + 30
    contract = ResponseContract.json_object()
    with execution_scope(config or ExecutionConfig()):
        value = _call_task(
            AgentPrompt("Return JSON.", "controlled test input"),
            RunLLMClient(client, "coordinator"),
            deadline=deadline,
            validator=lambda parsed: None,
            response_budget=response_budget,
            response_contract=contract,
            task_id="ordinary-OP-01",
        )
    return value, deadline, contract


def test_first_truncation_repairs_once_with_doubled_bounded_cap_and_same_contract():
    client = ScriptedClient(
        [result("", finish_reason="length"), result('{"results": []}')]
    )

    (parsed, repaired, _), deadline, contract = call(
        client, config=ExecutionConfig(llm_max_new_tokens=900)
    )

    assert parsed == {"results": []}
    assert repaired is True
    assert [kwargs["max_new_tokens"] for _, kwargs in client.calls] == [512, 900]
    assert all(kwargs["deadline"] == deadline for _, kwargs in client.calls)
    assert all(kwargs["response_contract"] == contract for _, kwargs in client.calls)


def test_truncation_repair_grows_from_inventory_budget_only_to_global_cap():
    client = ScriptedClient(
        [result("", finish_reason="length"), result('{"results": []}')]
    )
    call(client, response_budget=2048, config=ExecutionConfig(llm_max_new_tokens=4096))
    assert [kwargs["max_new_tokens"] for _, kwargs in client.calls] == [2048, 4096]


def test_malformed_json_repair_keeps_original_cap():
    client = ScriptedClient([result("not json"), result('{"results": []}')])
    (parsed, repaired, _), _, _ = call(client)
    assert parsed == {"results": []}
    assert repaired is True
    assert [kwargs["max_new_tokens"] for _, kwargs in client.calls] == [512, 512]


def test_json_object_config_ignores_native_schema_but_validates_and_repairs():
    client = ScriptedClient([result('{"results": []}'), result('{"results": []}')])
    schema = ResponseContract.json_schema({"type": "object"}, name="task_schema")
    validations = 0

    def validator(parsed):
        nonlocal validations
        validations += 1
        if validations == 1:
            raise AgentExecutionError("semantic validation failed")

    with execution_scope(ExecutionConfig(llm_response_mode="json_object")):
        parsed, repaired, _ = _call_task(
            AgentPrompt("Return JSON.", "input"),
            RunLLMClient(client, "coordinator"),
            deadline=time.monotonic() + 30,
            validator=validator,
            response_contract=schema,
            response_budget=128,
        )

    assert parsed == {"results": []}
    assert repaired is True
    assert validations == 2
    assert len(client.calls) == 2
    assert [kwargs["max_new_tokens"] for _, kwargs in client.calls] == [128, 128]
    assert all(
        kwargs["response_contract"] == ResponseContract.json_object()
        for _, kwargs in client.calls
    )


def test_json_schema_config_preserves_caller_contract():
    client = ScriptedClient([result('{"results": []}')])
    schema = ResponseContract.json_schema({"type": "object"}, name="task_schema")

    with execution_scope(ExecutionConfig(llm_response_mode="json_schema")):
        _call_task(
            AgentPrompt("Return JSON.", "input"),
            RunLLMClient(client, "coordinator"),
            deadline=time.monotonic() + 30,
            response_contract=schema,
        )

    assert len(client.calls) == 1
    assert client.calls[0][1]["response_contract"] is schema


def test_nontruncation_llm_error_does_not_retry():
    client = ScriptedClient([AgentLLMError("transport unavailable")])
    with pytest.raises(AgentLLMError, match="transport unavailable"):
        call(client)
    assert len(client.calls) == 1


def test_second_truncation_fails_after_exactly_two_calls(caplog):
    client = ScriptedClient(
        [
            result("private output one", finish_reason="length"),
            result("private output two", finish_reason="length"),
        ]
    )
    with pytest.raises(AgentLLMError, match="LLM output was truncated"):
        call(client)
    assert len(client.calls) == 2
    assert [kwargs["max_new_tokens"] for _, kwargs in client.calls] == [512, 1024]
    assert "task=ordinary-OP-01 stage=initial cap=512" in caplog.text
    assert "stage=repair cap=1024 repeated=true" in caplog.text
    assert "private output" not in caplog.text
    assert "controlled test input" not in caplog.text


def test_output_cap_hit_repair_stays_at_global_ceiling():
    client = ScriptedClient(
        [
            CompletionResult("", "offline-test", output_cap_hit=True),
            result('{"results": []}'),
        ]
    )
    (parsed, repaired, _), _, _ = call(
        client, config=ExecutionConfig(llm_max_new_tokens=256)
    )
    assert repaired and parsed == {"results": []}
    assert [kwargs["max_new_tokens"] for _, kwargs in client.calls] == [256, 256]


def test_only_repair_truncation_is_logged_as_first_truncation(caplog):
    client = ScriptedClient([result("not json"), result("", finish_reason="length")])
    with pytest.raises(AgentLLMError, match="LLM output was truncated"):
        call(client)
    assert len(client.calls) == 2
    assert "stage=repair cap=512 repeated=false" in caplog.text


def test_invalid_repair_logs_task_and_reference_without_private_payload(caplog):
    client = ScriptedClient(
        [result("private first payload"), result("private second payload")]
    )
    with pytest.raises(AgentExecutionError, match="not JSON"):
        call(client)
    assert len(client.calls) == 2
    assert "task=ordinary-OP-01 stage=initial reference=" in caplog.text
    assert "task=ordinary-OP-01 stage=repair reference=" in caplog.text
    assert "private" not in caplog.text


def test_parse_fallback_does_not_hide_second_attempt_transport_failure():
    client = ScriptedClient(
        [result("malformed first response"), AgentLLMError("transport unavailable")]
    )
    fallbacks = []
    with execution_scope(ExecutionConfig()):
        with pytest.raises(AgentLLMError, match="transport unavailable"):
            _call_task(
                AgentPrompt("Return JSON.", "input"),
                RunLLMClient(client, "coordinator"),
                deadline=time.monotonic() + 30,
            )
    assert len(client.calls) == 2
    assert fallbacks == []


@pytest.mark.parametrize("packet_budget", [None, 16_000])
def test_repair_reserves_instruction_budget_and_captures_actual_prompt(packet_budget):
    ceiling = packet_budget or 32_000
    prompt = AgentPrompt(
        "Return JSON.", "x" * (ceiling - 1_200 - len("Return JSON.") - 2)
    )
    error = AgentExecutionError(
        "explanation finding must be nonempty, trimmed, and at most 400 characters"
    )
    client = ScriptedClient([result('{"results": []}'), result('{"results": []}')])
    captured = []
    attempts = 0

    def validator(parsed):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise error

    with execution_scope(ExecutionConfig(agent_total_prompt_budget_chars=32_000)):
        parsed, repaired, completion = _call_task(
            prompt,
            RunLLMClient(client, "coordinator"),
            deadline=time.monotonic() + 30,
            validator=validator,
            repair_instruction="r" * 474,
            capture_prompt=captured.append,
            prompt_budget=packet_budget,
        )
    assert repaired and parsed == {"results": []}
    assert len(client.calls) == 2
    assert len(client.calls[1][0]) <= ceiling
    assert captured == [client.calls[1][0]]
    assert "VALIDATION FAILURE" in captured[0].user_context


def test_redundant_closing_delimiters_need_no_model_repair():
    client = ScriptedClient([result('{"results": []} ]} ]}')])
    (parsed, repaired, _), _, _ = call(client)
    assert parsed == {"results": []}
    assert repaired is False
    assert len(client.calls) == 1


@pytest.mark.parametrize("tail", [' {"results": []}', " explanation", ","])
def test_complete_json_followed_by_new_content_still_requires_repair(tail):
    client = ScriptedClient(
        [result('{"results": []}' + tail), result('{"results": []}')]
    )
    (parsed, repaired, _), _, _ = call(client)
    assert parsed == {"results": []}
    assert repaired is True
    assert len(client.calls) == 2
