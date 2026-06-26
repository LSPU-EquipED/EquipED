"""Tests for the LLM client retry and rate-limit handling."""

from __future__ import annotations

import json
import socket
from urllib import error

import pytest
from server.core.exceptions import (
    ConfigurationError,
    InfrastructureUnavailableError,
)
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
        self.timeout_args: list[float | None] = []

    def __call__(self, *args, **kwargs):
        self.calls += 1
        self.timeout_args.append(kwargs.get("timeout"))
        if self.calls <= len(self.responses):
            resp = self.responses[self.calls - 1]
            if isinstance(resp, Exception):
                raise resp
            return resp
        raise RuntimeError("No more mock responses")


def _make_http_error(
    code: int, retry_after: str | None = None
) -> error.HTTPError:
    """Create a mock HTTPError with optional Retry-After header."""
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = retry_after

    class _MockHeaders:
        def get(self, key, default=None):
            return headers.get(key, default)

    return error.HTTPError(
        url="http://example.com",
        code=code,
        msg=f"HTTP {code}",
        hdrs=_MockHeaders(),
        fp=None,
    )


def _make_client(**overrides) -> LocalLLMClient:
    defaults = dict(
        provider="openai_compatible",
        model="test-model",
        api_base="http://localhost:11434/v1",
        api_key=None,
    )
    defaults.update(overrides)
    return LocalLLMClient(**defaults)


_SUCCESS_BODY = json.dumps({
    "choices": [{"message": {"content": '{"summary":"ok","criterion_scores":[]}'}}]
})


# ---------------------------------------------------------------------------
# Retry-After parsing
# ---------------------------------------------------------------------------


def test_parse_retry_after_caps_at_max() -> None:
    """Retry-After values exceeding the cap should be clamped."""
    err = _make_http_error(429, retry_after="300")
    result = LocalLLMClient._parse_retry_after(err)
    assert result == _MAX_RETRY_AFTER_SECONDS


def test_parse_retry_after_returns_small_values_unchanged() -> None:
    """Retry-After values below the cap should pass through."""
    err = _make_http_error(429, retry_after="10")
    result = LocalLLMClient._parse_retry_after(err)
    assert result == 10.0


def test_parse_retry_after_returns_none_for_missing_header() -> None:
    """Missing Retry-After header should return None."""
    err = _make_http_error(429, retry_after=None)
    result = LocalLLMClient._parse_retry_after(err)
    assert result is None


def test_parse_retry_after_returns_none_for_invalid_value() -> None:
    """Non-numeric Retry-After should return None."""
    err = _make_http_error(429, retry_after="Wed, 21 Oct 2025 07:28:00 GMT")
    result = LocalLLMClient._parse_retry_after(err)
    assert result is None


# ---------------------------------------------------------------------------
# 429 Retry-After cap (existing behaviour preserved)
# ---------------------------------------------------------------------------


def test_429_retry_respects_capped_backoff(monkeypatch) -> None:
    """A 429 with a huge Retry-After should be capped, not stall indefinitely."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("server.core.llm.time.sleep", sleep_calls.append)

    client = _make_client()
    err_429 = _make_http_error(429, retry_after="300")
    opener = _FakeURLOpener([err_429, _FakeHTTPResponse(200, _SUCCESS_BODY)])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    result = client.generate("test prompt")

    assert result == '{"summary":"ok","criterion_scores":[]}'
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == _MAX_RETRY_AFTER_SECONDS


def test_429_retry_exhausts_after_max_retries(monkeypatch) -> None:
    """After 3 consecutive 429s, client raises InfrastructureUnavailableError."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("server.core.llm.time.sleep", sleep_calls.append)

    client = _make_client()
    err_429 = _make_http_error(429, retry_after="5")
    opener = _FakeURLOpener([err_429, err_429, err_429])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    with pytest.raises(InfrastructureUnavailableError) as exc_info:
        client.generate("test prompt")

    assert "HTTP 429" in str(exc_info.value)
    assert "3/3" in str(exc_info.value)
    # 2 sleeps between 3 attempts, each at 5s (Retry-After value).
    assert len(sleep_calls) == 2
    assert all(s == 5.0 for s in sleep_calls)


# ---------------------------------------------------------------------------
# 503 transient retry
# ---------------------------------------------------------------------------


def test_503_retries_then_succeeds(monkeypatch) -> None:
    """A 503 followed by success should return the successful response."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("server.core.llm.time.sleep", sleep_calls.append)

    client = _make_client()
    err_503 = _make_http_error(503)
    opener = _FakeURLOpener([err_503, _FakeHTTPResponse(200, _SUCCESS_BODY)])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    result = client.generate("test prompt")

    assert result == '{"summary":"ok","criterion_scores":[]}'
    assert opener.calls == 2
    # Exponential backoff: 2 * 2^0 = 2s
    assert sleep_calls == [2.0]


def test_503_exhausts_after_configured_attempts(monkeypatch) -> None:
    """503 on every attempt should raise after max_attempts with detail."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("server.core.llm.time.sleep", sleep_calls.append)

    client = _make_client(max_attempts=4)
    err_503 = _make_http_error(503)
    opener = _FakeURLOpener([err_503] * 5)
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    with pytest.raises(InfrastructureUnavailableError) as exc_info:
        client.generate("test prompt")

    assert "HTTP 503" in str(exc_info.value)
    assert "4/4" in str(exc_info.value)
    assert opener.calls == 4
    # 3 sleeps: backoff 2, 4, 8
    assert sleep_calls == [2.0, 4.0, 8.0]


# ---------------------------------------------------------------------------
# Non-retryable statuses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [401, 422])
def test_non_retryable_status_makes_single_call(
    status: int, monkeypatch
) -> None:
    """401/422 should NOT be retried — exactly one call, immediate raise."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("server.core.llm.time.sleep", sleep_calls.append)

    client = _make_client()
    err = _make_http_error(status)
    opener = _FakeURLOpener([err])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    with pytest.raises(InfrastructureUnavailableError) as exc_info:
        client.generate("test prompt")

    assert f"HTTP {status}" in str(exc_info.value)
    assert opener.calls == 1
    assert sleep_calls == []


# ---------------------------------------------------------------------------
# URLError / timeout transport retries
# ---------------------------------------------------------------------------


def test_urlerror_retries_then_succeeds(monkeypatch) -> None:
    """URLError on first attempt, success on second."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("server.core.llm.time.sleep", sleep_calls.append)

    client = _make_client()
    url_err = error.URLError("Connection refused")
    opener = _FakeURLOpener([url_err, _FakeHTTPResponse(200, _SUCCESS_BODY)])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    result = client.generate("test prompt")

    assert result == '{"summary":"ok","criterion_scores":[]}'
    assert opener.calls == 2
    assert sleep_calls == [2.0]


def test_urlerror_exhausts_with_useful_message(monkeypatch) -> None:
    """URLError on every attempt should raise with attempt count and reason."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("server.core.llm.time.sleep", sleep_calls.append)

    client = _make_client()
    url_err = error.URLError("Connection refused")
    opener = _FakeURLOpener([url_err, url_err, url_err])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    with pytest.raises(InfrastructureUnavailableError) as exc_info:
        client.generate("test prompt")

    msg = str(exc_info.value)
    assert "3/3" in msg
    assert "unreachable" in msg.lower()
    assert opener.calls == 3


def test_timeout_error_retries_then_succeeds(monkeypatch) -> None:
    """socket.timeout on first attempt, success on second."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("server.core.llm.time.sleep", sleep_calls.append)

    client = _make_client()
    timeout_err = socket.timeout("timed out")
    opener = _FakeURLOpener([timeout_err, _FakeHTTPResponse(200, _SUCCESS_BODY)])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    result = client.generate("test prompt")

    assert result == '{"summary":"ok","criterion_scores":[]}'
    assert opener.calls == 2


def test_connection_reset_retries(monkeypatch) -> None:
    """ConnectionResetError should be retried."""
    sleep_calls: list[float] = []
    monkeypatch.setattr("server.core.llm.time.sleep", sleep_calls.append)

    client = _make_client()
    reset_err = ConnectionResetError("Connection reset by peer")
    opener = _FakeURLOpener([reset_err, _FakeHTTPResponse(200, _SUCCESS_BODY)])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    result = client.generate("test prompt")
    assert result == '{"summary":"ok","criterion_scores":[]}'
    assert opener.calls == 2


# ---------------------------------------------------------------------------
# Timeout configuration
# ---------------------------------------------------------------------------


def test_request_timeout_passed_to_urlopen(monkeypatch) -> None:
    """Configured request_timeout should be forwarded to urlopen."""
    monkeypatch.setattr("server.core.llm.time.sleep", lambda _: None)

    client = _make_client(request_timeout=42.0)
    opener = _FakeURLOpener([_FakeHTTPResponse(200, _SUCCESS_BODY)])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    client.generate("test prompt")

    assert opener.timeout_args == [42.0]


def test_request_timeout_default_from_settings(monkeypatch) -> None:
    """When request_timeout is None, it should come from settings."""

    class _FakeSettings:
        llm_request_timeout_seconds = 99

    monkeypatch.setattr(
        "server.core.llm.get_settings", lambda: _FakeSettings()
    )
    monkeypatch.setattr("server.core.llm.time.sleep", lambda _: None)

    client = _make_client(request_timeout=None)
    opener = _FakeURLOpener([_FakeHTTPResponse(200, _SUCCESS_BODY)])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    client.generate("test prompt")

    assert opener.timeout_args == [99.0]


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def test_config_rejects_non_positive_timeout(monkeypatch) -> None:
    """LLM_REQUEST_TIMEOUT_SECONDS <= 0 should raise ConfigurationError."""
    from server.core import config as config_mod

    # Clear the cached settings so our env var takes effect.
    config_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "0")

    try:
        with pytest.raises(ConfigurationError, match="LLM_REQUEST_TIMEOUT_SECONDS"):
            config_mod.get_settings()
    finally:
        config_mod.get_settings.cache_clear()


def test_config_rejects_negative_timeout(monkeypatch) -> None:
    """Negative LLM_REQUEST_TIMEOUT_SECONDS should raise ConfigurationError."""
    from server.core import config as config_mod

    config_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "-5")

    try:
        with pytest.raises(ConfigurationError, match="LLM_REQUEST_TIMEOUT_SECONDS"):
            config_mod.get_settings()
    finally:
        config_mod.get_settings.cache_clear()


def test_config_accepts_valid_timeout(monkeypatch) -> None:
    """A positive LLM_REQUEST_TIMEOUT_SECONDS should be accepted."""
    from server.core import config as config_mod

    config_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "60")

    try:
        settings = config_mod.get_settings()
        assert settings.llm_request_timeout_seconds == 60
    finally:
        config_mod.get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Malformed 200 response
# ---------------------------------------------------------------------------


def test_malformed_json_200_raises_clear_error(monkeypatch) -> None:
    """A 200 with unparseable JSON should say the response was malformed."""
    monkeypatch.setattr("server.core.llm.time.sleep", lambda _: None)

    client = _make_client()
    opener = _FakeURLOpener([_FakeHTTPResponse(200, "not-json{{{")])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    with pytest.raises(InfrastructureUnavailableError) as exc_info:
        client.generate("test prompt")

    msg = str(exc_info.value)
    assert "malformed" in msg.lower() or "invalid" in msg.lower()
    assert "client could not be created" not in msg.lower()
    assert "1/3" in msg


def test_missing_keys_200_raises_clear_error(monkeypatch) -> None:
    """A 200 with valid JSON but wrong shape should say the response was malformed."""
    monkeypatch.setattr("server.core.llm.time.sleep", lambda _: None)

    client = _make_client()
    opener = _FakeURLOpener([_FakeHTTPResponse(200, json.dumps({"ok": True}))])
    monkeypatch.setattr("server.core.llm.request.urlopen", opener)

    with pytest.raises(InfrastructureUnavailableError) as exc_info:
        client.generate("test prompt")

    msg = str(exc_info.value)
    assert "malformed" in msg.lower() or "invalid" in msg.lower()
    assert "client could not be created" not in msg.lower()
