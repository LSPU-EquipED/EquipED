"""Tests for the LLM client retry and rate-limit handling."""

from __future__ import annotations

import json
from urllib import error

import pytest
from server.core.exceptions import InfrastructureUnavailableError
from server.core.llm import _MAX_RETRY_AFTER_SECONDS, LocalLLMClient


class _FakeHTTPResponse:
    """Simulates a urllib HTTP response."""

    def __init__(self, status_code: int, body: str, headers: dict | None = None):
        self.status = status_code
        self.code = status_code
        self._body = body
        self._headers = headers or {}

    def read(self):
        return self._body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _FakeURLOpener:
    """Mock urllib.request.urlopen for testing."""

    def __init__(self, responses: list):
        self.responses = responses
        self.calls = 0
        self.sleep_calls: list[float] = []

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.calls <= len(self.responses):
            resp = self.responses[self.calls - 1]
            if isinstance(resp, Exception):
                raise resp
            return resp
        raise RuntimeError("No more mock responses")


def _make_429_error(retry_after: str | None = None) -> error.HTTPError:
    """Create a mock 429 HTTPError with optional Retry-After header."""
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after

    class _MockHeaders:
        def get(self, key, default=None):
            return headers.get(key, default)

    return error.HTTPError(
        url="http://example.com",
        code=429,
        msg="Too Many Requests",
        hdrs=_MockHeaders(),
        fp=None,
    )


def test_parse_retry_after_caps_at_max(monkeypatch) -> None:
    """Retry-After values exceeding the cap should be clamped."""
    err = _make_429_error(retry_after="300")
    result = LocalLLMClient._parse_retry_after(err)
    assert result == _MAX_RETRY_AFTER_SECONDS


def test_parse_retry_after_returns_small_values_unchanged(monkeypatch) -> None:
    """Retry-After values below the cap should pass through."""
    err = _make_429_error(retry_after="10")
    result = LocalLLMClient._parse_retry_after(err)
    assert result == 10.0


def test_parse_retry_after_returns_none_for_missing_header(monkeypatch) -> None:
    """Missing Retry-After header should return None."""
    err = _make_429_error(retry_after=None)
    result = LocalLLMClient._parse_retry_after(err)
    assert result is None


def test_parse_retry_after_returns_none_for_invalid_value(monkeypatch) -> None:
    """Non-numeric Retry-After should return None."""
    err = _make_429_error(retry_after="Wed, 21 Oct 2025 07:28:00 GMT")
    result = LocalLLMClient._parse_retry_after(err)
    assert result is None


def test_429_retry_respects_capped_backoff(monkeypatch) -> None:
    """A 429 with a huge Retry-After should be capped, not stall indefinitely."""
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    monkeypatch.setattr("server.core.llm.time.sleep", fake_sleep)

    client = LocalLLMClient(
        provider="openai_compatible",
        model="test-model",
        api_base="http://localhost:11434/v1",
        api_key=None,
    )

    # First call: 429 with Retry-After=300 (should be capped to 60).
    # Second call: success.
    success_body = json.dumps({
        "choices": [{"message": {"content": '{"summary":"ok","criterion_scores":[]}'}}]
    })

    err_429 = _make_429_error(retry_after="300")

    opener = _FakeURLOpener([err_429, _FakeHTTPResponse(200, success_body)])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    result = client.generate("test prompt")

    assert result == '{"summary":"ok","criterion_scores":[]}'
    # Sleep should be capped at 60s, not 300s.
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == _MAX_RETRY_AFTER_SECONDS


def test_429_retry_exhausts_after_max_retries(monkeypatch) -> None:
    """After 3 consecutive 429s, client raises InfrastructureUnavailableError."""
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float):
        sleep_calls.append(seconds)

    monkeypatch.setattr("server.core.llm.time.sleep", fake_sleep)

    client = LocalLLMClient(
        provider="openai_compatible",
        model="test-model",
        api_base="http://localhost:11434/v1",
        api_key=None,
    )

    err_429 = _make_429_error(retry_after="5")
    opener = _FakeURLOpener([err_429, err_429, err_429])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    with pytest.raises(InfrastructureUnavailableError) as exc_info:
        client.generate("test prompt")

    # The 3rd 429 is raised directly (no retry on last attempt).
    assert "HTTP 429" in str(exc_info.value)
    # 2 sleeps (between retries 1-2 and 2-3), each at 5s (Retry-After value).
    assert len(sleep_calls) == 2
    assert all(s == 5.0 for s in sleep_calls)
