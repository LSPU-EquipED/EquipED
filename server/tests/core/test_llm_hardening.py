"""Deterministic contract tests for the bounded local LLM transport."""

from __future__ import annotations

import json
import threading
from types import MappingProxyType
from urllib import error

import pytest
from server.core import llm
from server.core.exceptions import ConfigurationError, InfrastructureUnavailableError


class Response:
    def __init__(self, body, headers=None):
        self.body = json.dumps(body).encode()
        self.headers = headers or {}

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class Settings:
    llm_request_timeout_seconds = 10
    llm_response_mode = "json_object"
    llm_inflight_limit = 1
    llm_rpm_limit = 0
    llm_tpm_limit = 0


def client(**kwargs):
    values = dict(
        provider="openai_compatible",
        model="m",
        api_base="http://localhost/v1",
        api_key=None,
    )
    values.update(kwargs)
    return llm.LocalLLMClient(**values)


@pytest.fixture(autouse=True)
def isolated_gates(monkeypatch):
    llm._GATES.clear()
    monkeypatch.setattr(llm, "get_settings", lambda: Settings())
    yield
    llm._GATES.clear()


def ok(**extra):
    return Response(
        {
            "model": "served",
            "choices": [{"message": {"content": " {} "}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            **extra,
        }
    )


def test_completion_result_is_deeply_immutable():
    result = llm.CompletionResult(
        "x", "m", rate_fields=MappingProxyType({"nested": (1,)})
    )
    with pytest.raises((AttributeError, TypeError)):
        result.content = "y"
    with pytest.raises(TypeError):
        result.rate_fields["x"] = 1


def test_generate_result_captures_usage_finish_reason_served_model_and_rate_fields(
    monkeypatch,
):
    response = ok()
    response.headers = {
        "X-RateLimit-Limit-Requests": "5",
        "X-Secret": "no",
        "Retry-After": "2",
    }
    monkeypatch.setattr(llm.request, "urlopen", lambda *a, **k: response)
    result = client().generate_result(
        "p", response_contract=llm.ResponseContract.json_object()
    )
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (
        2,
        3,
        5,
    )
    assert result.finish_reason == "stop" and result.served_model == "served"
    assert dict(result.rate_fields) == {
        "X-RateLimit-Limit-Requests": "5",
        "Retry-After": "2",
    }


def test_json_object_payload(monkeypatch):
    seen = []
    monkeypatch.setattr(
        llm.request,
        "urlopen",
        lambda req, **k: seen.append(json.loads(req.data)) or ok(),
    )
    client().generate_result("p", response_contract=llm.ResponseContract.json_object())
    assert seen[0]["response_format"] == {"type": "json_object"}


def test_json_schema_payload_uses_named_agent_schema(monkeypatch):
    seen = []
    schema = {"type": "object", "properties": {"score": {"type": "integer"}}}
    monkeypatch.setattr(
        llm.request,
        "urlopen",
        lambda req, **k: seen.append(json.loads(req.data)) or ok(),
    )
    client().generate_result(
        "p",
        response_contract=llm.ResponseContract.json_schema(schema, "agent_response"),
    )
    assert seen[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "agent_response", "schema": schema, "strict": True},
    }


def test_invalid_or_missing_schema_fails_before_network_without_downgrade(monkeypatch):
    calls = []
    monkeypatch.setattr(llm.request, "urlopen", lambda *a, **k: calls.append(1))
    for schema in (None, {}, "bad"):
        with pytest.raises(ConfigurationError):
            contract = llm.ResponseContract.json_schema(schema)
            client().generate_result("p", response_contract=contract)
    assert not calls


def test_clients_with_same_target_share_inflight_gate():
    a = client()
    b = client()
    assert a is not b
    assert llm._gate_for((a.provider, a.api_base, a.model), 1) is llm._gate_for(
        (b.provider, b.api_base, b.model), 1
    )


def test_quota_disabled_local_calls_can_overlap(monkeypatch):
    Settings.llm_inflight_limit = 2
    entered = threading.Barrier(2)
    ready = threading.Event()
    release = threading.Event()

    def opener(*args, **kwargs):
        entered.wait()
        ready.set()
        release.wait()
        return ok()

    monkeypatch.setattr(llm.request, "urlopen", opener)
    threads = [
        threading.Thread(target=client(provider="local").generate, args=("p",))
        for _ in range(2)
    ]
    for t in threads:
        t.start()
    ready.wait()
    release.set()
    for t in threads:
        t.join()


def test_rpm_gate_paces_requests_with_fake_clock(monkeypatch):
    Settings.llm_rpm_limit = 1
    clock = iter([0.0, 0.0, 0.0, 60.0, 60.0])
    monkeypatch.setattr(llm.time, "monotonic", lambda: next(clock))
    gate = llm._Gate(1)
    gate.acquire(100, 1, 0, 1)
    with pytest.raises(InfrastructureUnavailableError):
        gate.acquire(0, 1, 0, 1)


def test_tpm_reservation_prevents_concurrent_overcommit():
    gate = llm._Gate(2)
    gate.acquire(llm.time.monotonic() + 10, 0, 5, 5)
    with pytest.raises(InfrastructureUnavailableError):
        gate.acquire(llm.time.monotonic() + 10, 0, 5, 5)


def test_single_request_over_tpm_fails_before_network():
    gate = llm._Gate(1)
    with pytest.raises(InfrastructureUnavailableError):
        gate.acquire(10, 0, 5, 6)


def test_deadline_includes_gate_wait_and_first_urlopen_uses_remaining(monkeypatch):
    seen = []
    times = iter([0.0, 0.0, 2.0, 3.0, 3.0])
    monkeypatch.setattr(llm.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(
        llm.request, "urlopen", lambda *a, **k: seen.append(k["timeout"]) or ok()
    )
    client(request_timeout=5).generate_result(
        "p", response_contract=llm.ResponseContract.json_object()
    )
    assert seen == [2.0]


def test_retry_after_exceeding_remaining_deadline_does_not_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    monkeypatch.setattr(
        llm.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(
            error.HTTPError("u", 429, "x", {"Retry-After": "9"}, None)
        ),
    )
    with pytest.raises(InfrastructureUnavailableError):
        client(request_timeout=1).generate_result(
            "p", response_contract=llm.ResponseContract.json_object()
        )
    assert sleeps == []


def test_provider_error_body_sentinel_not_exposed(monkeypatch):
    sentinel = "SECRET_PROVIDER_BODY"
    monkeypatch.setattr(
        llm.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(
            error.HTTPError("u", 400, sentinel, {}, None)
        ),
    )
    with pytest.raises(InfrastructureUnavailableError) as exc:
        client().generate_result(
            "p", response_contract=llm.ResponseContract.json_object()
        )
    assert sentinel not in str(exc.value)
