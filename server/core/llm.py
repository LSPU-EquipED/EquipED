"""Lazy local/open-source LLM client singleton."""

from __future__ import annotations

import json
import socket
import time
from functools import lru_cache
from typing import Any
from urllib import error, request

from .config import get_settings
from .exceptions import (
    ConfigurationError,
    InfrastructureUnavailableError,
)

_MAX_RETRY_AFTER_SECONDS = 60

# HTTP statuses that indicate a transient condition worth retrying.
_RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

# Transport-level exceptions that indicate a transient connectivity issue.
_RETRYABLE_TRANSPORT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    socket.timeout,
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    ConnectionRefusedError,
)


class LocalLLMClient:
    """Reusable wrapper that can target local or open-source chat backends."""

    def __init__(
        self,
        provider: str,
        model: str,
        api_base: str | None,
        api_key: str | None,
        *,
        max_attempts: int = 3,
        initial_backoff: float = 2.0,
        max_backoff: float = 60.0,
        request_timeout: float | None = None,
    ):
        self.provider = provider
        self.model = model
        self.api_base = api_base
        self.api_key = api_key
        self.max_attempts = max_attempts
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.request_timeout = request_timeout

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_new_tokens: int = 512,
    ) -> str:
        if self.provider in {"local", "openai_compatible", "open-source"}:
            return self._generate_openai_compatible(
                prompt,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
            )
        raise ConfigurationError(f"Unsupported LLM provider: {self.provider}")

    def _generate_openai_compatible(
        self,
        prompt: str,
        *,
        temperature: float,
        max_new_tokens: int,
    ) -> str:
        base_url = (self.api_base or "http://localhost:11434/v1").rstrip("/")
        url = f"{base_url}/chat/completions"
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": temperature,
                "max_tokens": max_new_tokens,
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "EquipED/0.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        timeout = self.request_timeout
        if timeout is None:
            timeout = float(get_settings().llm_request_timeout_seconds)

        last_exc: BaseException | None = None
        for attempt in range(1, self.max_attempts + 1):
            req = request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return str(data["choices"][0]["message"]["content"]).strip()
            except error.HTTPError as exc:
                last_exc = exc
                if (
                    exc.code in _RETRYABLE_HTTP_STATUSES
                    and attempt < self.max_attempts
                ):
                    backoff = self._compute_backoff(exc, attempt)
                    time.sleep(backoff)
                    continue
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    pass
                raise InfrastructureUnavailableError(
                    f"LLM endpoint returned HTTP {exc.code} "
                    f"after {attempt}/{self.max_attempts} attempts: "
                    f"{body or exc.reason}"
                ) from exc
            except error.URLError as exc:
                last_exc = exc
                if attempt < self.max_attempts:
                    backoff = min(
                        self.initial_backoff * (2 ** (attempt - 1)),
                        self.max_backoff,
                    )
                    time.sleep(backoff)
                    continue
                reason = getattr(exc, "reason", exc)
                raise InfrastructureUnavailableError(
                    f"LLM endpoint unreachable after "
                    f"{attempt}/{self.max_attempts} attempts: {reason}"
                ) from exc
            except _RETRYABLE_TRANSPORT_EXCEPTIONS as exc:
                last_exc = exc
                if attempt < self.max_attempts:
                    backoff = min(
                        self.initial_backoff * (2 ** (attempt - 1)),
                        self.max_backoff,
                    )
                    time.sleep(backoff)
                    continue
                raise InfrastructureUnavailableError(
                    f"LLM transport error after "
                    f"{attempt}/{self.max_attempts} attempts: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                raise InfrastructureUnavailableError(
                    f"LLM provider returned an invalid or malformed response "
                    f"(HTTP 200) after "
                    f"{attempt}/{self.max_attempts} attempts: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            except Exception as exc:  # pragma: no cover - client init guard
                raise InfrastructureUnavailableError(
                    f"Unexpected LLM client error: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc

        # Exhausted all attempts via retryable paths without raising inside loop.
        detail = f"{type(last_exc).__name__}: {last_exc}" if last_exc else "unknown"
        raise InfrastructureUnavailableError(
            f"LLM call exhausted {self.max_attempts} attempts: {detail}"
        )

    def _compute_backoff(
        self, exc: error.HTTPError, attempt: int
    ) -> float:
        """Compute backoff for a retryable HTTP error.

        Uses Retry-After when present (capped), otherwise deterministic
        exponential backoff: initial_backoff * 2^(attempt-1), capped.
        """
        retry_after = self._parse_retry_after(exc)
        if retry_after is not None:
            return retry_after
        return min(
            self.initial_backoff * (2 ** (attempt - 1)),
            self.max_backoff,
        )

    @staticmethod
    def _parse_retry_after(exc: error.HTTPError) -> float | None:
        """Extract Retry-After seconds from a response header, capped."""
        retry_after = exc.headers.get("Retry-After")
        if retry_after is None:
            return None
        try:
            value = float(retry_after.strip())
        except (ValueError, TypeError):
            return None
        # Cap to prevent indefinite stalls from bad upstream responses.
        return min(value, _MAX_RETRY_AFTER_SECONDS)


@lru_cache(maxsize=1)
def get_llm_client() -> Any:
    """Create the LLM client only when it is explicitly requested."""

    settings = get_settings()
    return LocalLLMClient(
        provider=settings.llm_provider,
        model=settings.llm_model_name,
        api_base=settings.llm_api_base,
        api_key=settings.llm_api_key,
        request_timeout=float(settings.llm_request_timeout_seconds),
    )


def get_llm_model_name() -> str:
    """Expose the configured default model name for downstream callers."""

    return get_settings().llm_model_name


__all__ = ["LocalLLMClient", "get_llm_client", "get_llm_model_name"]
