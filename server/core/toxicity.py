"""Dedicated toxicity classifier client and endpoint locality guard.

Toxicity assessment uses its own client configuration (``TOXICITY_API_BASE``,
``TOXICITY_MODEL_NAME``, ``TOXICITY_API_KEY``) and never reuses the global
evaluation LLM client or its arbitrary ``LLM_API_BASE``.

The endpoint locality guard (:func:`validate_toxicity_endpoint`) enforces
that only local/self-hosted services are reachable — public IPs, external
DNS names that resolve to public addresses, and URLs with credentials /
query / fragment are rejected.  DNS errors fail closed.
"""

from __future__ import annotations

from typing import Any

from server.core.endpoint_security import is_private_endpoint
from server.core.exceptions import ConfigurationError


def validate_toxicity_endpoint(url: str) -> tuple[bool, str]:
    """Return ``(is_allowed, reason)`` for a toxicity classifier URL.

    Checks in order:
    1. Scheme is http or https.
    2. No embedded credentials, query string, or fragment.
    3. Hostname is a known safe local name, OR all resolved IPs are
       private/loopback/link-local/ULA.
    4. DNS errors (including ambiguous / no-address results) fail closed.
    """
    allowed, reason = is_private_endpoint(url)
    if not allowed:
        return False, reason
    return True, ""


def get_toxicity_client() -> Any:
    """Create and return a configured toxicity classifier client.

    Returns a :class:`~server.core.llm.LocalLLMClient` configured with the
    dedicated toxicity settings.  Raises :class:`ConfigurationError` if:
    * ``toxicity_assessment_enabled`` is False.
    * The configured endpoint fails the locality guard.
    * The required ``toxicity_api_base`` or ``toxicity_model_name`` is missing.

    Never falls back to the global evaluation LLM client.
    """
    from server.core.config import get_settings
    from server.core.llm import LocalLLMClient

    settings = get_settings()

    if not settings.toxicity_assessment_enabled:
        raise ConfigurationError("Toxicity assessment is not enabled.")

    api_base = settings.toxicity_api_base
    model = settings.toxicity_model_name

    if not api_base:
        raise ConfigurationError(
            "TOXICITY_API_BASE is required when toxicity assessment is enabled."
        )
    if not model:
        raise ConfigurationError(
            "TOXICITY_MODEL_NAME is required when toxicity assessment is enabled."
        )

    allowed, reason = validate_toxicity_endpoint(api_base)
    if not allowed:
        raise ConfigurationError(
            f"Toxicity endpoint rejected by locality guard: {reason}"
        )

    return LocalLLMClient(
        provider="openai_compatible",
        model=model,
        api_base=api_base.rstrip("/"),
        api_key=settings.toxicity_api_key,
        request_timeout=float(settings.toxicity_request_timeout_seconds),
    )
