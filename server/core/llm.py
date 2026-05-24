"""Lazy local/open-source LLM client singleton."""

from __future__ import annotations

import json
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


class LocalLLMClient:
    """Reusable wrapper that can target local or open-source chat backends."""

    def __init__(
        self,
        provider: str,
        model: str,
        api_base: str | None,
        api_key: str | None,
    ):
        self.provider = provider
        self.model = model
        self.api_base = api_base
        self.api_key = api_key

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

        max_retries = 3
        for attempt in range(max_retries):
            req = request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return str(data["choices"][0]["message"]["content"]).strip()
            except error.HTTPError as exc:
                # Handle 429 Too Many Requests with Retry-After or backoff
                if exc.code == 429 and attempt < max_retries - 1:
                    retry_after = self._parse_retry_after(exc)
                    if retry_after is not None:
                        time.sleep(retry_after)
                    else:
                        # Exponential backoff: 2s, 4s, 8s
                        time.sleep(2 ** (attempt + 1))
                    continue
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    pass
                raise InfrastructureUnavailableError(
                    f"LLM endpoint returned HTTP {exc.code}: {body or exc.reason}"
                ) from exc
            except error.URLError as exc:
                raise InfrastructureUnavailableError(
                    "Local/open-source LLM endpoint could not be reached"
                ) from exc
            except Exception as exc:  # pragma: no cover - client init guard
                raise InfrastructureUnavailableError(
                    "Local/open-source LLM client could not be created"
                ) from exc

        # Should not reach here, but guard against it
        raise InfrastructureUnavailableError(
            "LLM call exhausted retries after rate-limit backoff"
        )

    @staticmethod
    def _parse_retry_after(exc: error.HTTPError) -> float | None:
        """Extract Retry-After seconds from a 429 response header, capped."""
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
    )


def get_llm_model_name() -> str:
    """Expose the configured default model name for downstream callers."""

    return get_settings().llm_model_name


__all__ = ["LocalLLMClient", "get_llm_client", "get_llm_model_name"]
