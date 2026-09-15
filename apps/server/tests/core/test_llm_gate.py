"""Characterization tests for the local LLM admission gate."""

from __future__ import annotations

import json
import threading
from urllib import error

import pytest
from server.core import llm
from server.core.exceptions import InfrastructureUnavailableError


class _Response:
    headers = {}

    def read(self, amount=None):
        body = json.dumps(
            {"model": "m", "choices": [{"message": {"content": "ok"}}]}
        ).encode()
        return body if amount is None else body[:amount]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class _Settings:
    llm_request_timeout_seconds = 2
    llm_response_mode = "json_object"
    llm_inflight_limit = 2
    llm_rpm_limit = 0
    llm_tpm_limit = 0
    llm_local_quota_enabled = False


@pytest.fixture(autouse=True)
def reset_gates(monkeypatch):
    llm._GATES.clear()
    monkeypatch.setattr(llm, "get_settings", lambda: _Settings())
    yield
    llm._GATES.clear()


def test_release_reconciles_the_matching_ticket_event():
    gate = llm._Gate(2)
    first = gate.acquire(llm.time.monotonic() + 1, 0, 0, 11)
    second = gate.acquire(llm.time.monotonic() + 1, 0, 0, 22)
    gate.release(first, 101)
    gate.release(second, 202)
    assert gate.events[first.id][1] == 101
    assert gate.events[second.id][1] == 202


def test_retries_create_one_rpm_event_per_physical_attempt(monkeypatch):
    calls = []

    def opener(*_args, **_kwargs):
        calls.append(1)
        if len(calls) < 3:
            raise error.HTTPError("u", 500, "retry", {}, None)
        return _Response()

    monkeypatch.setattr(llm.request, "urlopen", opener)
    monkeypatch.setattr(llm.time, "sleep", lambda _delay: None)
    _Settings.llm_local_quota_enabled = True
    _Settings.llm_rpm_limit = 10
    result = llm.LocalLLMClient(
        "p", "m", "http://localhost/v1", None, initial_backoff=0
    ).generate_result("x")
    gate = next(iter(llm._GATES.values()))
    assert result.attempts == 3 and len(calls) == 3 and len(gate.events) == 3


def test_retry_after_blocks_equivalent_peer_until_release():
    a = llm._gate_for(llm._key("p", "HTTP://LOCALHOST:80/v1/", "m"), 2)
    peer = llm._gate_for(llm._key("p", "http://localhost/v1", "m"), 2)
    assert a is peer
    a.block_for(0.2)
    entered = threading.Event()
    done = threading.Event()

    def waiter():
        entered.set()
        ticket = a.acquire(llm.time.monotonic() + 1, 0, 0, 1)
        a.release(ticket)
        done.set()

    thread = threading.Thread(target=waiter)
    thread.start()
    entered.wait(1)
    assert not done.wait(0.05)
    with a.condition:
        a.blocked_until = llm.time.monotonic()
        a.condition.notify_all()
    thread.join(2)
    assert not thread.is_alive() and done.is_set()


def test_waiters_are_fifo():
    gate = llm._Gate(1)
    held = gate.acquire(llm.time.monotonic() + 1, 0, 0, 1)
    order, threads = [], []

    def wait(number):
        ticket = gate.acquire(llm.time.monotonic() + 1, 0, 0, 1)
        order.append(number)
        gate.release(ticket)

    for number in range(3):
        thread = threading.Thread(target=wait, args=(number,))
        threads.append(thread)
        thread.start()
        while len(gate.waiters) < number + 1:
            threading.Event().wait(0.001)
    gate.release(held)
    for thread in threads:
        thread.join(2)
        assert not thread.is_alive()
    assert order == [0, 1, 2]


def test_timed_out_head_waiter_is_removed_and_next_proceeds():
    gate = llm._Gate(1)
    held = gate.acquire(llm.time.monotonic() + 1, 0, 0, 1)
    first = threading.Thread(
        target=lambda: pytest.raises(
            InfrastructureUnavailableError,
            gate.acquire,
            llm.time.monotonic() + 0.05,
            0,
            0,
            1,
        )
    )
    result = []
    first.start()
    while len(gate.waiters) < 1:
        threading.Event().wait(0.001)
    second = threading.Thread(
        target=lambda: result.append(gate.acquire(llm.time.monotonic() + 1, 0, 0, 1))
    )
    second.start()
    first.join(2)
    gate.release(held)
    second.join(2)
    assert not first.is_alive() and not second.is_alive() and result
    gate.release(result[0])


def test_double_and_foreign_release_do_not_touch_active_ticket():
    gate = llm._Gate(2)
    active = gate.acquire(llm.time.monotonic() + 1, 0, 0, 3)
    gate.release(llm._GateTicket(999, 1, active.admitted_at), 99)
    gate.release(active, 7)
    gate.release(active, 99)
    assert not gate.active and gate.events[active.id][1] == 7


def test_quota_disabled_allows_overlap_but_enabled_rpm_does_not():
    gate = llm._Gate(2)
    one = gate.acquire(llm.time.monotonic() + 1, 0, 0, 1)
    two = gate.acquire(llm.time.monotonic() + 1, 0, 0, 1)
    gate.release(one)
    gate.release(two)
    gate = llm._Gate(2)
    gate.acquire(llm.time.monotonic() + 1, 1, 0, 1)
    with pytest.raises(InfrastructureUnavailableError):
        gate.acquire(llm.time.monotonic() + 0.02, 1, 0, 1)


def test_estimate_over_tpm_fails_before_admission():
    gate = llm._Gate(1)
    with pytest.raises(InfrastructureUnavailableError):
        gate.acquire(llm.time.monotonic() + 1, 0, 5, 6)


def test_gate_key_normalizes_target_but_keeps_model_distinct():
    assert llm._key("P", "HTTP://LOCALHOST:80/v1/", "m") == llm._key(
        "p", "http://localhost/v1", "m"
    )
    assert llm._key("p", "http://localhost/v1", "m") != llm._key(
        "p", "http://localhost/v1", "other"
    )
