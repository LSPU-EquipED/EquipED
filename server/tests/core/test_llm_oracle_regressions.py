"""Regression evidence for the local LLM gate, transport, and readiness oracle."""

from __future__ import annotations

import json
import threading
import time
from types import MappingProxyType
from urllib import error

import pytest
from server.core import llm
from server.core.exceptions import ConfigurationError, InfrastructureUnavailableError


class Settings:
    llm_request_timeout_seconds = 1
    llm_readiness_timeout_seconds = 1
    llm_response_mode = "json_object"
    llm_inflight_limit = 1
    llm_rpm_limit = llm_tpm_limit = 0
    llm_local_quota_enabled = False
    llm_provider = "local"
    llm_api_base = "http://localhost/v1"
    llm_api_key = None
    llm_model_name = "model"


class Response:
    headers = {}

    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self, *_):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class RawResponse(Response):
    def __init__(self, body):
        self.body = body


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    llm._GATES.clear()
    monkeypatch.setattr(llm, "get_settings", lambda: Settings())
    yield
    llm._GATES.clear()


def test_expired_deadlines_leave_gate_empty(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(llm.time, "monotonic", lambda: now[0])
    gate = llm._Gate(1)
    for deadline in (now[0], now[0] - 1):
        with pytest.raises(InfrastructureUnavailableError):
            gate.acquire(deadline, 1, 100, 10)
    assert not gate.active and not gate.events and not gate.waiters
    ticket = gate.acquire(now[0] + 1, 1, 100, 10)
    assert gate.active == {ticket.id: ticket}
    assert not gate.waiters
    assert list(gate.events) == [ticket.id]
    gate.release(ticket)


def test_aged_active_ticket_remains_capacity_until_release(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(llm.time, "monotonic", lambda: now[0])
    gate = llm._Gate(1)
    original = gate.acquire(20, 1, 100, 4)
    now[0] += 61
    acquired = threading.Event()
    replacement = []

    def wait_for_capacity():
        replacement.append(gate.acquire(now[0] + 10, 1, 100, 4))
        acquired.set()

    waiter = threading.Thread(target=wait_for_capacity)
    waiter.start()
    time.sleep(0.01)
    assert not acquired.is_set() and len(gate.active) == 1 and gate.waiters
    gate.release(original)
    assert acquired.wait(0.2)
    waiter.join(1)
    gate.release(replacement[0])
    assert not gate.active and not gate.waiters


def test_http_429_release_and_block_holds_peer_until_cooldown(monkeypatch):
    first_entered = threading.Event()
    allow_first = threading.Event()
    b_waiting = threading.Event()
    calls = []
    lock = threading.Lock()

    def opener(req, **_):
        with lock:
            calls.append((threading.current_thread().name, time.monotonic()))
            n = len(calls)
        if n == 1:
            first_entered.set()
            allow_first.wait(0.2)
            exc = error.HTTPError(
                req.full_url, 429, "busy", {"Retry-After": "0.04"}, None
            )
            raise exc
        return Response({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(llm.request, "urlopen", opener)
    client = llm.LocalLLMClient(
        "local",
        "model",
        "http://localhost/v1",
        None,
        max_attempts=2,
        initial_backoff=0,
        request_timeout=0.5,
    )
    results = []

    def run(name):
        if name == "B":
            b_waiting.set()
        results.append(client.generate_result(name, max_new_tokens=1))

    a = threading.Thread(target=run, args=("A",), name="A")
    b = threading.Thread(target=run, args=("B",), name="B")
    a.start()
    first_entered.wait(0.2)
    b.start()
    b_waiting.wait(0.2)
    allow_first.set()
    time.sleep(0.01)
    with lock:
        assert len(calls) == 1
    a.join(1)
    b.join(1)
    assert not a.is_alive() and not b.is_alive() and len(results) == 2
    assert calls[1][1] - calls[0][1] >= 0.03


def test_terminal_http_429_keeps_peer_out_until_cooldown(monkeypatch):
    first_entered = threading.Event()
    second_started = threading.Event()
    first_release = threading.Barrier(2)
    calls = []
    results = {}
    lock = threading.Lock()

    def opener(req, **_):
        prompt = json.loads(req.data)["messages"][0]["content"]
        with lock:
            calls.append((prompt, time.monotonic()))
        if prompt == "A":
            first_entered.set()
            first_release.wait(0.5)
            raise error.HTTPError(
                req.full_url, 429, "busy", {"Retry-After": "0.04"}, None
            )
        assert prompt == "B"
        return Response({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(llm.request, "urlopen", opener)
    client = llm.LocalLLMClient(
        "local",
        "model",
        "http://localhost/v1",
        None,
        max_attempts=1,
        initial_backoff=0,
        request_timeout=0.5,
    )

    def run(prompt):
        if prompt == "B":
            second_started.set()
        try:
            results[prompt] = client.generate_result(prompt, max_new_tokens=1)
        except InfrastructureUnavailableError as exc:
            results[prompt] = exc

    a = threading.Thread(target=run, args=("A",), name="A")
    b = threading.Thread(target=run, args=("B",), name="B")
    a.start()
    assert first_entered.wait(0.2)
    b.start()
    assert second_started.wait(0.2)
    first_release.wait(0.2)
    a.join(1)
    b.join(1)

    assert not a.is_alive() and not b.is_alive()
    assert isinstance(results["A"], InfrastructureUnavailableError)
    assert str(results["A"]) == "LLM request failed: HTTP 429 (1/1)"
    assert results["B"].content == "ok"
    assert [prompt for prompt, _ in calls] == ["A", "B"]
    assert calls[1][1] - calls[0][1] >= 0.03
    assert not llm._GATES[llm._key("local", "http://localhost/v1", "model")].active


def test_release_and_block_cooldown_is_monotonic(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(llm.time, "monotonic", lambda: now[0])
    gate = llm._Gate(3)

    first = gate.acquire(1, 0, 0, 1)
    second = gate.acquire(1, 0, 0, 1)
    third = gate.acquire(1, 0, 0, 1)
    gate.release_and_block(first, 5)
    assert gate.blocked_until == 5

    now[0] = 1
    gate.release_and_block(second, 10)
    assert gate.blocked_until == 11

    now[0] = 2
    gate.release_and_block(third, 1)
    assert gate.blocked_until == 11
    assert not gate.active and not gate.waiters


@pytest.mark.parametrize(
    "body, expected, raw",
    [
        ({"ready": True}, True, False),
        ({}, False, False),
        ({"ready": False}, False, False),
        ({"ready": "yes"}, False, False),
        ({"ready": True, "x": 1}, False, False),
        ("bad", False, True),
    ],
)
def test_readiness_requires_exact_canary(monkeypatch, body, expected, raw):
    model_requests = []
    payloads = []

    def opener(req, **_):
        if req.full_url.endswith("/models"):
            model_requests.append(req)
            return Response({"data": [{"id": "model"}]})
        payloads.append(json.loads(req.data))
        content = body if raw else json.dumps(body)
        return Response({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(llm.request, "urlopen", opener)
    if expected:
        llm.probe_local_model_readiness()
    else:
        with pytest.raises(InfrastructureUnavailableError) as exc:
            llm.probe_local_model_readiness()
        assert str(exc.value) == "Local model readiness check failed"
    assert len(model_requests) == 1 and len(payloads) == 1
    assert payloads[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "readiness_canary",
            "schema": {
                "type": "object",
                "properties": {"ready": {"type": "boolean"}},
                "required": ["ready"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }


def test_readiness_rejects_raw_non_json_completion(monkeypatch):
    payloads = []

    def opener(req, **_):
        if req.full_url.endswith("/models"):
            return Response({"data": [{"id": "model"}]})
        payloads.append(json.loads(req.data))
        return RawResponse(b'{"choices":[{"message":{"content":"ready"}}]}')

    monkeypatch.setattr(llm.request, "urlopen", opener)
    with pytest.raises(InfrastructureUnavailableError):
        llm.probe_local_model_readiness()
    assert len(payloads) == 1


@pytest.mark.parametrize("finish", ["length"])
def test_readiness_rejects_output_cap(monkeypatch, finish):
    def opener(req, **_):
        if req.full_url.endswith("/models"):
            return Response({"data": [{"id": "model"}]})
        return Response(
            {
                "choices": [
                    {"message": {"content": '{"ready": true}'}, "finish_reason": finish}
                ]
            }
        )

    monkeypatch.setattr(llm.request, "urlopen", opener)
    with pytest.raises(InfrastructureUnavailableError):
        llm.probe_local_model_readiness()


def test_readiness_http_rejection_is_generic(monkeypatch):
    def opener(req, **_):
        if req.full_url.endswith("/models"):
            return Response({"data": [{"id": "model"}]})
        raise error.HTTPError(req.full_url, 400, "secret detail", {}, None)

    monkeypatch.setattr(llm.request, "urlopen", opener)
    with pytest.raises(
        InfrastructureUnavailableError, match="^Local model readiness check failed$"
    ):
        llm.probe_local_model_readiness()


def test_response_contract_freezes_nested_mutable_inputs_and_exposure():
    nested = {"nested": {"values": [1]}}
    source = {"properties": {"items": [nested]}}
    contract = llm.ResponseContract(
        mode="json_schema",
        schema_name="x",
        schema=MappingProxyType(source),
    )
    nested["nested"]["values"].append(2)
    assert contract.schema["properties"]["items"][0]["nested"]["values"] == (1,)
    with pytest.raises(TypeError):
        contract.schema["properties"] = {}
    with pytest.raises(TypeError):
        contract.schema["properties"]["items"][0]["nested"]["values"] = ()
    with pytest.raises(AttributeError):
        contract.schema["properties"]["items"].append({})


@pytest.mark.parametrize(
    "args",
    [("bad",), ("json_object", "name", {"x": 1}), ("json_schema", None, {"x": 1})],
)
def test_response_contract_rejects_invalid_direct_construction(args):
    with pytest.raises(ConfigurationError):
        llm.ResponseContract(*args)
