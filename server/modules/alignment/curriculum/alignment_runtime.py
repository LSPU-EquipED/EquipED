"""Alignment-specific LLM runtime policy for the curriculum-alignment check.

Owns the transport/retry boundary for the single alignment LLM call:

- At most one initial attempt plus one transient retry.
- Retry only timeout / connection / HTTP 429 / HTTP 5xx (and HTTP 408, a
  server-side request timeout).
- Never retry HTTP 400/401/403/404/413, schema/parse errors, or config
  errors.
- Per-attempt timeout is capped at 60 seconds.
- No automatic model fallback: the worker is always the same model the
  caller configured; nothing here swaps models or constructs a replacement
  client on model failure.

Other agents' client behavior is preserved: this module only wraps whatever
client the caller passes in, and ``server/modules/agents/base.py`` keeps its
own retry/fallback handling untouched.
"""

from __future__ import annotations

import json
import socket
import time
from typing import Any
from urllib import error as urllib_error

from server.core.config import get_settings
from server.core.exceptions import ConfigurationError
from server.core.llm import LocalLLMClient

# Runtime policy: initial attempt + at most one transient retry.
MAX_ATTEMPTS = 2

# Phase 2A contract: per-attempt timeout must never exceed 60s.
MAX_ATTEMPT_TIMEOUT_SECONDS = 60.0

# Deterministic short pause between the initial attempt and the one retry.
RETRY_BACKOFF_SECONDS = 1.0

# Transient HTTP signals: request timeout (408), rate limit (429), and any
# 5xx. Everything else -- including 400/401/403/404/413 -- fails immediately.
_RETRYABLE_HTTP_STATUSES = frozenset({408, 429, *range(500, 600)})

# Transport-level signals for "timeout" or "connection" problems.
_RETRYABLE_TRANSPORT_TYPES: tuple[type[BaseException], ...] = (
    TimeoutError,
    socket.timeout,
    ConnectionResetError,
    ConnectionAbortedError,
    ConnectionRefusedError,
    BrokenPipeError,
)

# Mirrors the supported set in server/core/llm.py so preflight can reject an
# unusable provider before any attempt spends capacity.
_SUPPORTED_PROVIDERS = frozenset({"local", "openai_compatible", "open-source"})


class AlignmentCallError(Exception):
    """Base error for alignment LLM calls."""

    kind = "alignment_call_error"

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        kind: str | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.kind = kind or self.__class__.kind


class AlignmentConfigError(AlignmentCallError):
    """Invalid client configuration; raised before any capacity is spent."""

    kind = "config"


class AlignmentTransientError(AlignmentCallError):
    """A timeout/connection/429/5xx failure that may be retried once."""

    kind = "transient"


class AlignmentPermanentError(AlignmentCallError):
    """A non-retryable failure (4xx, schema/parse, unexpected)."""

    kind = "permanent"


class AlignmentResponseError(AlignmentPermanentError):
    """The model returned text that fails strict parsing or coverage."""

    kind = "response_schema"


def preflight_client(client: Any) -> None:
    """Validate configuration before spending any attempt or token budget.

    Duck-typed test doubles only need a callable ``generate``. Real
    ``LocalLLMClient`` instances are additionally checked against the
    supported provider set, a non-empty model name, and a positive resolvable
    timeout -- configuration/model errors fail here, not after a wasted call.
    """
    if not callable(getattr(client, "generate", None)):
        raise AlignmentConfigError(
            "alignment LLM client must expose a callable generate()",
            attempts=0,
        )
    if not isinstance(client, LocalLLMClient):
        return
    if client.provider not in _SUPPORTED_PROVIDERS:
        raise AlignmentConfigError(
            f"unsupported LLM provider {client.provider!r}",
            attempts=0,
        )
    if not client.model or not str(client.model).strip():
        raise AlignmentConfigError(
            "LLM model name is not configured",
            attempts=0,
        )
    timeout = _resolve_timeout(client)
    if timeout <= 0:
        raise AlignmentConfigError(
            "LLM request timeout must be positive",
            attempts=0,
        )


def _resolve_timeout(client: LocalLLMClient) -> float:
    if client.request_timeout is not None:
        return float(client.request_timeout)
    return float(get_settings().llm_request_timeout_seconds)


def _as_single_attempt(client: Any) -> Any:
    """Return a worker that performs exactly one HTTP attempt per ``generate``.

    The shared ``LocalLLMClient`` retries internally (default 3 attempts), so
    the alignment boundary derives a sibling configured with ``max_attempts=1``
    and the policy-capped per-attempt timeout; the retry loop lives here so
    retry count/outcome can be recorded in provenance. The derived worker
    keeps the same provider, model, api_base, and api_key -- there is no model
    fallback. Duck-typed clients (test doubles) pass through unchanged.
    """
    if not isinstance(client, LocalLLMClient):
        return client
    timeout = min(max(_resolve_timeout(client), 1.0), MAX_ATTEMPT_TIMEOUT_SECONDS)
    return LocalLLMClient(
        provider=client.provider,
        model=client.model,
        api_base=client.api_base,
        api_key=client.api_key,
        max_attempts=1,
        initial_backoff=client.initial_backoff,
        max_backoff=client.max_backoff,
        request_timeout=timeout,
    )


def _http_code(exc: BaseException | None) -> int | None:
    if isinstance(exc, urllib_error.HTTPError):
        return exc.code
    return None


def _urllib_reason(exc: BaseException | None) -> BaseException | str | None:
    if isinstance(exc, urllib_error.URLError):
        return exc.reason
    return None


def _transport_kind(reason: BaseException) -> str:
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout"
    return "connection"


def _classify_exception(exc: BaseException, *, attempts: int) -> AlignmentCallError:
    """Map any client/transport exception to a typed alignment error.

    ``HTTPError`` subclasses ``URLError``, so HTTP codes are checked before
    transport reasons. ``InfrastructureUnavailableError`` from the shared
    client preserves the underlying error in ``__cause__``; both the raised
    exception and its cause are inspected so the real client path and raw
    exception-raising test doubles classify identically.
    """
    if isinstance(exc, AlignmentCallError):
        return exc
    if isinstance(exc, ConfigurationError):
        return AlignmentConfigError(str(exc)[:200], attempts=0)
    cause = getattr(exc, "__cause__", None)

    for candidate in (exc, cause):
        code = _http_code(candidate)
        if code is not None:
            if code in _RETRYABLE_HTTP_STATUSES:
                return AlignmentTransientError(
                    f"retryable HTTP {code}",
                    attempts=attempts,
                    kind=f"http_{code}",
                )
            return AlignmentPermanentError(
                f"non-retryable HTTP {code}",
                attempts=attempts,
                kind=f"http_{code}",
            )

    for candidate in (exc, cause):
        reason = _urllib_reason(candidate)
        if reason is not None:
            if isinstance(reason, _RETRYABLE_TRANSPORT_TYPES):
                kind = _transport_kind(reason)
                return AlignmentTransientError(
                    f"{kind}: {type(reason).__name__}",
                    attempts=attempts,
                    kind=kind,
                )
            return AlignmentPermanentError(
                "endpoint unreachable",
                attempts=attempts,
                kind="endpoint_unreachable",
            )

    for candidate in (exc, cause):
        if isinstance(candidate, _RETRYABLE_TRANSPORT_TYPES):
            kind = _transport_kind(candidate)
            return AlignmentTransientError(
                f"{kind}: {type(candidate).__name__}",
                attempts=attempts,
                kind=kind,
            )

    parse_types = (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError)
    if isinstance(exc, parse_types) or isinstance(cause, parse_types):
        return AlignmentPermanentError(
            "malformed or invalid provider response",
            attempts=attempts,
            kind="invalid_response",
        )
    return AlignmentPermanentError(
        "unexpected alignment LLM failure",
        attempts=attempts,
        kind="unexpected",
    )


def call_with_retry(
    client: Any,
    prompt: str,
    *,
    temperature: float,
    max_new_tokens: int,
    backoff_seconds: float = RETRY_BACKOFF_SECONDS,
) -> tuple[str, int]:
    """Call ``client.generate`` with the alignment retry policy.

    Returns ``(response_text, attempts_made)`` on success. Raises a typed
    ``AlignmentCallError`` (carrying the number of attempts made) on failure.
    Never swaps models and never falls back to another client.
    """
    preflight_client(client)
    worker = _as_single_attempt(client)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            text = worker.generate(
                prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
            )
            return text, attempt
        except Exception as exc:
            classified = _classify_exception(exc, attempts=attempt)
            if (
                isinstance(classified, AlignmentTransientError)
                and attempt < MAX_ATTEMPTS
            ):
                time.sleep(backoff_seconds)
                continue
            raise classified from exc
    raise AlignmentPermanentError(
        "alignment LLM call exhausted all attempts",
        attempts=MAX_ATTEMPTS,
        kind="unexpected",
    )


__all__ = [
    "AlignmentCallError",
    "AlignmentConfigError",
    "AlignmentTransientError",
    "AlignmentPermanentError",
    "AlignmentResponseError",
    "MAX_ATTEMPTS",
    "MAX_ATTEMPT_TIMEOUT_SECONDS",
    "RETRY_BACKOFF_SECONDS",
    "preflight_client",
    "call_with_retry",
]
