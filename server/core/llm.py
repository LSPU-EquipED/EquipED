"""Bounded, private OpenAI-compatible LLM transport."""

from __future__ import annotations

import json
import math
import re
import threading
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import Any
from urllib import error, request
from urllib.parse import urlsplit

from .config import get_settings
from .endpoint_security import is_private_endpoint
from .exceptions import ConfigurationError, InfrastructureUnavailableError

_RETRYABLE = frozenset({408, 429, 500, 502, 503, 504})
_MAX_RETRY_AFTER_SECONDS = 60.0
_GATES: dict[tuple, _ProviderGate] = {}
_GATES_LOCK = threading.Lock()
_MAX_USAGE = 10_000_000
_MAX_RESPONSE_BYTES = 1 * 1024 * 1024


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value):
    if isinstance(value, MappingProxyType):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


def _bounded_int(value):
    """Return a provider count only when it is a genuine bounded integer."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= _MAX_USAGE
    ):
        return None
    return value


@dataclass(frozen=True, slots=True)
class ResponseContract:
    """Immutable response-format contract supplied for one completion."""

    mode: str
    schema_name: str | None = None
    schema: Mapping | None = None

    @classmethod
    def json_object(cls) -> ResponseContract:
        return cls("json_object")

    @classmethod
    def json_schema(cls, schema, name: str = "agent_response") -> ResponseContract:
        if not isinstance(schema, Mapping) or not schema:
            raise ConfigurationError("Invalid bounded JSON Schema contract")
        if (
            not isinstance(name, str)
            or not 1 <= len(name) <= 64
            or not name.replace("_", "a").isalnum()
        ):
            raise ConfigurationError("Invalid bounded JSON Schema contract")
        return cls("json_schema", name, _freeze(schema))  # type: ignore[arg-type]

    def __post_init__(self) -> None:
        if self.mode not in {"json_object", "json_schema"}:
            raise ConfigurationError("Invalid response contract")
        if self.mode == "json_object":
            if self.schema_name is not None or self.schema is not None:
                raise ConfigurationError("Invalid response contract")
            return
        if (
            not isinstance(self.schema_name, str)
            or not 1 <= len(self.schema_name) <= 64
            or not self.schema_name.replace("_", "a").isalnum()
            or not isinstance(self.schema, Mapping)
            or not self.schema
        ):
            raise ConfigurationError("Invalid response contract")
        object.__setattr__(self, "schema", _freeze(self.schema))


READY_RESPONSE_CONTRACT = ResponseContract.json_schema(
    {
        "type": "object",
        "properties": {"ready": {"type": "boolean"}},
        "required": ["ready"],
        "additionalProperties": False,
    },
    name="readiness_canary",
)


@dataclass(frozen=True, slots=True)
class CompletionResult:
    """Deeply immutable, bounded completion metadata."""

    content: str
    served_model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    wall_seconds: float | None = None
    provider_seconds: float | None = None
    attempts: int = 1
    requested_max_tokens: int | None = None
    rate_fields: MappingProxyType | None = None
    output_cap_hit: bool = False
    response_format_downgraded: bool = False


@dataclass(frozen=True, slots=True)
class _GateTicket:
    id: int
    estimated_tokens: int
    admitted_at: float


class _ProviderGate:
    """FIFO admission gate with one quota event per physical attempt."""

    def __init__(self, limit: int):
        self.limit = limit
        self.condition = threading.Condition()
        self.waiters = deque()
        self.active: dict[int, _GateTicket] = {}
        self.events: dict[int, tuple[float, int]] = {}
        self.order = deque()
        self.next_id = 0
        self.blocked_until = 0.0

    def _purge(self, now: float) -> None:
        while self.order and now - self.events[self.order[0]][0] >= 60:
            self.events.pop(self.order.popleft(), None)

    def acquire(
        self, deadline: float, rpm: int, tpm: int, estimate: int
    ) -> _GateTicket:
        if tpm and estimate > tpm:
            raise InfrastructureUnavailableError("LLM request exceeds token quota")
        waiter = object()
        with self.condition:
            self.waiters.append(waiter)
            try:
                while True:
                    now = time.monotonic()
                    self._purge(now)
                    if self.waiters[0] is waiter and deadline - now <= 0:
                        self.waiters.popleft()
                        raise InfrastructureUnavailableError(
                            "LLM request deadline exceeded"
                        )
                    used = sum(self.events[i][1] for i in self.order)
                    allowed = (
                        self.waiters[0] is waiter
                        and now >= self.blocked_until
                        and len(self.active) < self.limit
                        and (not rpm or len(self.events) < rpm)
                        and (not tpm or used + estimate <= tpm)
                    )
                    if allowed:
                        self.waiters.popleft()
                        self.next_id += 1
                        ticket = _GateTicket(self.next_id, estimate, now)
                        self.active[ticket.id] = ticket
                        self.events[ticket.id] = (now, estimate)
                        self.order.append(ticket.id)
                        return ticket
                    remaining = deadline - now
                    if remaining <= 0:
                        raise InfrastructureUnavailableError(
                            "LLM request deadline exceeded"
                        )
                    waits = [remaining, 0.25]
                    if self.blocked_until > now:
                        waits.append(self.blocked_until - now)
                    if self.order:
                        waits.append(60 - (now - self.events[self.order[0]][0]))
                    self.condition.wait(max(0.001, min(waits)))
            except BaseException:
                if waiter in self.waiters:
                    self.waiters.remove(waiter)
                self.condition.notify_all()
                raise

    def release(self, ticket: _GateTicket, actual_tokens=None) -> None:
        with self.condition:
            if (
                not isinstance(ticket, _GateTicket)
                or self.active.get(ticket.id) != ticket
            ):
                return
            self.active.pop(ticket.id)
            if isinstance(actual_tokens, int) and 0 <= actual_tokens <= 10_000_000:
                event = self.events.get(ticket.id)
                if event is not None:
                    self.events[ticket.id] = (event[0], actual_tokens)
            self.condition.notify_all()

    def block_for(self, delay: float) -> None:
        with self.condition:
            self.blocked_until = max(
                self.blocked_until, time.monotonic() + min(max(0, delay), 60)
            )
            self.condition.notify_all()

    def release_and_block(self, ticket, delay, actual_tokens=None) -> None:
        """Release this attempt and impose cooldown atomically."""
        with self.condition:
            if (
                not isinstance(ticket, _GateTicket)
                or self.active.get(ticket.id) != ticket
            ):
                return
            self.active.pop(ticket.id)
            if isinstance(actual_tokens, int) and 0 <= actual_tokens <= _MAX_USAGE:
                event = self.events.get(ticket.id)
                if event is not None:
                    self.events[ticket.id] = (event[0], actual_tokens)
            bounded = min(max(0.0, delay), _MAX_RETRY_AFTER_SECONDS)
            self.blocked_until = max(self.blocked_until, time.monotonic() + bounded)
            self.condition.notify_all()


_Gate = _ProviderGate


def _key(provider, base, model):
    if isinstance(base, tuple):
        return (
            str(provider).lower(),
            str(base[0]).lower(),
            str(base[1]).lower(),
            80,
            "/",
            model,
        )
    parsed = urlsplit(base or "http://localhost:11434/v1")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    return (
        provider.lower(),
        parsed.scheme.lower(),
        (parsed.hostname or "").lower(),
        port,
        parsed.path.rstrip("/") or "/",
        model,
    )


def _gate_for(key, limit):
    with _GATES_LOCK:
        return _GATES.setdefault(
            key if isinstance(key, tuple) and len(key) == 6 else _key(*key),
            _ProviderGate(limit),
        )


class LocalLLMClient:
    """Issue bounded local chat-completion requests."""

    def __init__(
        self,
        provider,
        model,
        api_base,
        api_key,
        *,
        max_attempts=3,
        initial_backoff=2.0,
        max_backoff=60.0,
        request_timeout=None,
    ):
        self.provider, self.model, self.api_base, self.api_key = (
            provider,
            model,
            api_base,
            api_key,
        )
        self.max_attempts, self.initial_backoff, self.max_backoff = (
            max_attempts,
            initial_backoff,
            max_backoff,
        )
        self.request_timeout = request_timeout

    @staticmethod
    def _parse_retry_after(exc):
        try:
            return min(
                max(float(exc.headers.get("Retry-After", "")), 0),
                _MAX_RETRY_AFTER_SECONDS,
            )
        except (ValueError, TypeError, AttributeError):
            return None

    @staticmethod
    def _compute_backoff(attempt, initial=2.0, maximum=60.0):
        return min(initial * 2 ** (attempt - 1), maximum)

    def generate_result(
        self,
        prompt,
        *,
        temperature=0.2,
        max_new_tokens=512,
        deadline=None,
        response_contract=None,
    ):
        settings = get_settings()
        base = self.api_base or "http://localhost:11434/v1"
        allowed_hosts = getattr(settings, "llm_allowed_endpoints", ())
        allowed, _ = (
            is_private_endpoint(base, allowed_hosts=allowed_hosts)
            if allowed_hosts
            else is_private_endpoint(base)
        )
        if not allowed:
            raise InfrastructureUnavailableError("Local model is unavailable")
        contract = response_contract
        if contract is None:
            if getattr(settings, "llm_response_mode", "json_object") == "json_schema":
                raise ConfigurationError(
                    "Configured json_schema response mode requires an explicit schema"
                )
            contract = ResponseContract.json_object()
        if not isinstance(contract, ResponseContract):
            raise ConfigurationError("Invalid response contract")
        end = deadline or time.monotonic() + (
            self.request_timeout or settings.llm_request_timeout_seconds
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": contract.mode},
            "temperature": temperature,
            "max_tokens": max_new_tokens,
        }
        if contract.mode == "json_schema":
            payload["response_format"]["json_schema"] = {
                "name": contract.schema_name,
                "schema": _thaw(contract.schema),
                "strict": True,
            }
        gate = _gate_for(
            _key(self.provider, base, self.model),
            getattr(settings, "llm_inflight_limit", 1),
        )
        last = None
        retry_delay = None
        started = time.monotonic()
        estimate = max_new_tokens + max(1, len(prompt) // 4)
        attempt = 0
        response_format_downgraded = False
        for attempt in range(1, self.max_attempts + 1):
            quota = getattr(settings, "llm_local_quota_enabled", False)
            ticket = gate.acquire(
                end,
                getattr(settings, "llm_rpm_limit", 0) if quota else 0,
                getattr(settings, "llm_tpm_limit", 0) if quota else 0,
                estimate,
            )
            released = False
            try:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    raise InfrastructureUnavailableError(
                        "LLM request deadline exceeded"
                    )
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "EquipED/0.1.0",
                }
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                req = request.Request(
                    base.rstrip("/") + "/chat/completions",
                    data=json.dumps(payload).encode(),
                    headers=headers,
                    method="POST",
                )
                with request.urlopen(req, timeout=remaining) as response:
                    response_headers = getattr(response, "headers", {})
                    content_length = None
                    if hasattr(response_headers, "get"):
                        raw_content_length = response_headers.get("Content-Length")
                        if raw_content_length is None and hasattr(
                            response_headers, "items"
                        ):
                            for k, v in response_headers.items():
                                if str(k).lower() == "content-length":
                                    raw_content_length = v
                                    break
                        if raw_content_length is not None:
                            try:
                                parsed_cl = int(raw_content_length)
                                if parsed_cl >= 0:
                                    content_length = parsed_cl
                            except (ValueError, TypeError):
                                content_length = None

                    if (
                        content_length is not None
                        and content_length > _MAX_RESPONSE_BYTES
                    ):
                        raise ValueError(
                            "LLM response body exceeds maximum allowed size"
                        )

                    raw_body = response.read(_MAX_RESPONSE_BYTES + 1)

                    if len(raw_body) > _MAX_RESPONSE_BYTES:
                        raise ValueError(
                            "LLM response body exceeds maximum allowed size"
                        )

                    data = json.loads(raw_body)
                choice = data["choices"][0]
                message = choice["message"]
                usage = data.get("usage") or {}
                if not isinstance(message.get("content"), str):
                    raise ValueError("missing content")
                prompt_tokens = _bounded_int(usage.get("prompt_tokens"))
                completion_tokens = _bounded_int(usage.get("completion_tokens"))
                total_tokens = _bounded_int(usage.get("total_tokens"))
                gate.release(ticket, total_tokens)
                rates = MappingProxyType(
                    {
                        k: v
                        for k, v in response_headers.items()
                        if k.lower()
                        in {
                            "retry-after",
                            "x-ratelimit-limit-requests",
                            "x-ratelimit-remaining-requests",
                            "x-ratelimit-reset-requests",
                            "x-ratelimit-limit-tokens",
                            "x-ratelimit-remaining-tokens",
                        }
                        and len(str(v)) <= 64
                    }
                )
                provider_seconds = data.get("provider_seconds")
                if (
                    isinstance(provider_seconds, bool)
                    or not isinstance(provider_seconds, (int, float))
                    or not math.isfinite(provider_seconds)
                    or not 0 <= provider_seconds <= 3600
                ):
                    provider_seconds = None
                return CompletionResult(
                    content=message["content"].strip(),
                    served_model=str(data.get("model") or self.model),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    finish_reason=choice.get("finish_reason"),
                    wall_seconds=time.monotonic() - started,
                    provider_seconds=provider_seconds,
                    attempts=attempt,
                    requested_max_tokens=max_new_tokens,
                    rate_fields=rates,
                    output_cap_hit=choice.get("finish_reason") == "length",
                    response_format_downgraded=response_format_downgraded,
                )
            except error.HTTPError as exc:
                last = exc
                status = exc.code
                is_schema_fallback = status == 400 and contract.mode == "json_schema"
                if is_schema_fallback:
                    response_format_downgraded = True
                    payload["response_format"] = {"type": "json_object"}
                    if attempt < self.max_attempts:
                        retry_delay = 0.0
                elif status == 429:
                    retry_delay = self._parse_retry_after(exc)
                    if retry_delay is None:
                        retry_delay = self._compute_backoff(
                            attempt, self.initial_backoff, self.max_backoff
                        )
                    gate.release_and_block(ticket, retry_delay)
                    ticket = None
                    released = True
                if (
                    status not in _RETRYABLE and not is_schema_fallback
                ) or attempt == self.max_attempts:
                    break
                if not is_schema_fallback and status != 429:
                    retry_delay = self._compute_backoff(
                        attempt, self.initial_backoff, self.max_backoff
                    )
            except (
                error.URLError,
                TimeoutError,
                ConnectionError,
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                last = exc
                if isinstance(
                    exc, (json.JSONDecodeError, KeyError, TypeError, ValueError)
                ):
                    break
                if attempt == self.max_attempts:
                    break
                retry_delay = self._compute_backoff(
                    attempt, self.initial_backoff, self.max_backoff
                )
            finally:
                if ticket is not None and not released:
                    gate.release(ticket)
            delay = retry_delay
            remaining = end - time.monotonic()
            if delay is None or remaining <= delay:
                break
            time.sleep(float(delay))
        if isinstance(last, error.HTTPError):
            detail = f"HTTP {last.code} ({attempt}/{self.max_attempts})"
        elif isinstance(last, (error.URLError, TimeoutError, ConnectionError)):
            detail = f"endpoint unreachable ({attempt}/{self.max_attempts})"
        else:
            detail = f"malformed LLM response ({attempt}/{self.max_attempts})"
        raise InfrastructureUnavailableError(f"LLM request failed: {detail}") from last

    def generate(self, prompt, **kwargs):
        return self.generate_result(prompt, **kwargs).content


def parse_json_payload(raw: str) -> dict[str, Any]:
    """Parse JSON from LLM responses, stripping code fences or preambles."""
    if not isinstance(raw, str):
        raise ValueError("raw response must be a string")
    payload = raw.strip()
    match = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$", payload, flags=re.IGNORECASE | re.DOTALL
    )
    if match:
        payload = match.group(1).strip()
    elif not payload.startswith("{") and not payload.startswith("["):
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start : end + 1]
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError(f"expected JSON object, got {type(parsed).__name__}")
    return parsed


def probe_local_model_readiness(*, probe=None, canary=None, required_contract=None):
    """Perform a bounded, locality-first readiness check for the configured model."""
    try:
        settings = get_settings()
        if settings.llm_provider not in {"local", "openai_compatible", "open-source"}:
            raise ValueError
        base = settings.llm_api_base or "http://localhost:11434/v1"
        allowed_hosts = getattr(settings, "llm_allowed_endpoints", ())
        allowed, _ = (
            is_private_endpoint(base, allowed_hosts=allowed_hosts)
            if allowed_hosts
            else is_private_endpoint(base)
        )
        if not allowed:
            raise ValueError
        timeout = min(max(float(settings.llm_readiness_timeout_seconds), 1.0), 30.0)
        if probe is None:
            probe_headers = {"User-Agent": "EquipED/0.1.0"}
            if settings.llm_api_key:
                probe_headers["Authorization"] = f"Bearer {settings.llm_api_key}"
            req = request.Request(
                base.rstrip("/") + "/models",
                headers=probe_headers,
            )
            with request.urlopen(req, timeout=timeout) as response:
                models = json.loads(response.read(1_000_000)).get("data", [])
        else:
            models = probe(base, settings.llm_api_key, timeout)
        if isinstance(models, dict):
            models = models.get("data", [])
        if settings.llm_model_name not in {
            str(item.get("id", "")) for item in models if isinstance(item, dict)
        }:
            raise ValueError
        contract = required_contract or READY_RESPONSE_CONTRACT
        if contract is not None:
            if (
                not isinstance(contract, ResponseContract)
                or contract.mode != "json_schema"
            ):
                raise ValueError
            if canary is not None:
                result = canary(contract)
            else:
                result = LocalLLMClient(
                    settings.llm_provider,
                    settings.llm_model_name,
                    base,
                    settings.llm_api_key,
                    request_timeout=timeout,
                ).generate_result(
                    'Return JSON: {"ready": true}',
                    max_new_tokens=32,
                    deadline=time.monotonic() + timeout,
                    response_contract=contract,
                )
            if not isinstance(result, CompletionResult) or result.output_cap_hit:
                raise ValueError
            parsed = parse_json_payload(result.content)
            if parsed != {"ready": True}:
                raise ValueError
        return None
    except Exception as exc:
        raise InfrastructureUnavailableError(
            "Local model readiness check failed"
        ) from exc


@lru_cache(maxsize=1)
def get_llm_client():
    s = get_settings()
    return LocalLLMClient(
        s.llm_provider,
        s.llm_model_name,
        s.llm_api_base,
        s.llm_api_key,
        request_timeout=float(s.llm_request_timeout_seconds),
    )


@lru_cache(maxsize=8)
def get_llm_client_for_agent(agent_name):
    s = get_settings()
    return LocalLLMClient(
        s.llm_provider,
        s.get_agent_model(agent_name),
        s.llm_api_base,
        s.llm_api_key,
        request_timeout=float(s.llm_request_timeout_seconds),
    )


def get_llm_model_name():
    return get_settings().llm_model_name


__all__ = [
    "ResponseContract",
    "CompletionResult",
    "_GateTicket",
    "_ProviderGate",
    "_Gate",
    "LocalLLMClient",
    "get_llm_client",
    "get_llm_client_for_agent",
    "get_llm_model_name",
    "probe_local_model_readiness",
]
