"""Oracle characterization tests for the local LLM transport contract."""

from __future__ import annotations

import json
from types import MappingProxyType
from urllib import error

import pytest
from server.core import llm, toxicity
from server.core.exceptions import ConfigurationError, InfrastructureUnavailableError


class _Response:
    headers = {"X-RateLimit-Limit-Requests": "5", "Provider-Seconds": "2"}

    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class _Settings:
    llm_request_timeout_seconds = 5
    llm_response_mode = "json_object"
    llm_inflight_limit = 1
    llm_rpm_limit = llm_tpm_limit = 0
    llm_local_quota_enabled = False


def _client(**kwargs):
    values = dict(
        provider="local",
        model="model",
        api_base="http://localhost/v1",
        api_key="secret",
    )  # noqa: E501
    values.update(kwargs)
    return llm.LocalLLMClient(**values)


def _ok(**kwargs):
    return _Response(
        {
            "model": "served",
            "choices": [{"message": {"content": " {} "}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            **kwargs,
        }
    )


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    llm._GATES.clear()
    monkeypatch.setattr(_Settings, "llm_response_mode", "json_object")
    monkeypatch.setattr(llm, "get_settings", lambda: _Settings())
    yield
    llm._GATES.clear()


def test_one_client_preserves_each_response_contract_and_freezes_callers(monkeypatch):
    payloads = []
    monkeypatch.setattr(
        llm.request,
        "urlopen",
        lambda req, **_: payloads.append(json.loads(req.data)) or _ok(),
    )  # noqa: E501
    schema_a = {"type": "object", "properties": {"a": {"type": "string"}}}
    schema_b = {"type": "object", "properties": {"b": {"type": "integer"}}}
    client = _client()
    client.generate_result("p", response_contract=llm.ResponseContract.json_object())
    client.generate_result(
        "p", response_contract=llm.ResponseContract.json_schema(schema_a, "a_contract")
    )  # noqa: E501
    client.generate_result(
        "p", response_contract=llm.ResponseContract.json_schema(schema_b, "b_contract")
    )  # noqa: E501
    schema_a["properties"]["a"]["type"] = "boolean"
    assert payloads[0]["response_format"] == {"type": "json_object"}
    assert payloads[1]["response_format"]["json_schema"]["name"] == "a_contract"
    assert payloads[2]["response_format"]["json_schema"]["name"] == "b_contract"
    assert payloads[1]["response_format"]["json_schema"]["strict"] is True
    assert (
        payloads[1]["response_format"]["json_schema"]["schema"]["properties"]["a"][
            "type"
        ]
        == "string"
    )  # noqa: E501


def test_configured_schema_mode_requires_contract_before_network(monkeypatch):
    _Settings.llm_response_mode = "json_schema"
    calls = []
    monkeypatch.setattr(llm.request, "urlopen", lambda *args, **kwargs: calls.append(1))
    with pytest.raises(ConfigurationError):
        _client().generate_result("p")
    assert not calls


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8/v1",
        "http://user:pass@localhost/v1",
        "http://localhost/v1?q=1",
        "http://localhost/v1#fragment",
        "ftp://localhost/v1",
        "http://unresolved.invalid/v1",
    ],
)
def test_locality_rejection_precedes_request(monkeypatch, url):
    monkeypatch.setattr(llm, "is_private_endpoint", lambda value: (False, "rejected"))
    monkeypatch.setattr(
        llm.request, "urlopen", lambda *args, **kwargs: pytest.fail("network")
    )  # noqa: E501
    with pytest.raises(InfrastructureUnavailableError) as exc:
        _client(api_base=url).generate_result("p")
    assert "secret" not in str(exc.value) and url not in str(exc.value)


def test_completion_metadata_is_bounded_and_deeply_immutable(monkeypatch):
    response = _ok(
        provider_seconds=999999999,
        usage={"prompt_tokens": -1, "completion_tokens": True, "total_tokens": "5"},
    )  # noqa: E501
    response.headers = {"X-RateLimit-Limit-Requests": "x" * 65}
    monkeypatch.setattr(llm.request, "urlopen", lambda *args, **kwargs: response)
    result = _client().generate_result("p")
    assert (
        result.prompt_tokens is None
        and result.completion_tokens is None
        and result.total_tokens is None
    )  # noqa: E501
    assert result.provider_seconds is None and result.output_cap_hit
    assert isinstance(result.rate_fields, MappingProxyType) and not result.rate_fields


def test_provider_and_http_errors_do_not_expose_body_or_key(monkeypatch):
    sentinel = "PROVIDER_SECRET_BODY"
    monkeypatch.setattr(
        llm.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            error.HTTPError("u", 400, sentinel, {}, None)
        ),
    )  # noqa: E501
    with pytest.raises(InfrastructureUnavailableError) as exc:
        _client().generate_result("p")
    assert sentinel not in str(exc.value) and "secret" not in str(exc.value)


def test_toxicity_uses_same_locality_guard(monkeypatch):
    monkeypatch.setattr(
        toxicity, "is_private_endpoint", lambda value: (False, "public address")
    )  # noqa: E501
    allowed, reason = toxicity.validate_toxicity_endpoint("http://example.test/v1")
    assert not allowed and "public" in reason


def test_readiness_probe_is_public_and_performs_local_canary(monkeypatch):
    """The readiness gate must not silently skip the configured contract."""
    assert callable(llm.probe_local_model_readiness)
