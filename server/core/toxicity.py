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

import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

from server.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Known safe hostnames that resolve to loopback or private addresses
# on every development / Docker host.  These bypass DNS resolution.
_SAFE_LOCAL_NAMES: frozenset[str] = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
    "[::1]",
    "0.0.0.0",
    "localhost.localdomain",
    "localhost6",
    "localhost6.localdomain6",
    "host.docker.internal",
    "docker.host.internal",
    "gateway.docker.internal",
})

# Maximum seconds to wait for DNS resolution.
_DNS_TIMEOUT_SECONDS = 5.0


def validate_toxicity_endpoint(url: str) -> tuple[bool, str]:
    """Return ``(is_allowed, reason)`` for a toxicity classifier URL.

    Checks in order:
    1. Scheme is http or https.
    2. No embedded credentials, query string, or fragment.
    3. Hostname is a known safe local name, OR all resolved IPs are
       private/loopback/link-local/ULA.
    4. DNS errors (including ambiguous / no-address results) fail closed.
    """
    parsed = urlparse(url)

    # --- Scheme --------------------------------------------------------
    if parsed.scheme not in ("http", "https"):
        return False, f"Scheme '{parsed.scheme}' is not http or https"

    # --- Credentials / query / fragment --------------------------------
    if parsed.username or parsed.password:
        return False, "URL must not contain embedded credentials"
    if parsed.query:
        return False, "URL must not contain a query string"
    if parsed.fragment:
        return False, "URL must not contain a fragment"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL has no hostname"

    # --- Known safe names (bypass DNS) ---------------------------------
    if hostname.lower() in _SAFE_LOCAL_NAMES:
        return True, ""

    # --- DNS resolution guard ------------------------------------------
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_DNS_TIMEOUT_SECONDS)
    try:
        try:
            addrs = socket.getaddrinfo(hostname, None)
        except OSError as exc:
            return (
                False,
                f"Hostname '{hostname}' DNS resolution failed ({exc.args[1]})",
            )

        if not addrs:
            return False, f"Hostname '{hostname}' resolved to no addresses"

        ips: list[str] = []
        for family, _type, _proto, _canon, sockaddr in addrs:
            ip = sockaddr[0]
            # Deduplicate and strip IPv6 zone IDs
            clean = ip.split("%")[0]
            if clean not in ips:
                ips.append(clean)

        for ip in ips:
            if not _is_private_ip(ip):
                return (
                    False,
                    f"Hostname '{hostname}' resolved to public IP {ip}",
                )

        return True, ""
    finally:
        socket.setdefaulttimeout(old_timeout)


def _is_private_ip(ip_str: str) -> bool:
    """Return True when *ip_str* is loopback, private, link-local, or ULA."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    if addr.is_loopback:
        return True
    if addr.is_private:
        return True
    if addr.is_link_local:
        return True
    # Unique Local Address (IPv6 ULA, fc00::/7)
    if isinstance(addr, ipaddress.IPv6Address):
        # fc00::/7 — first byte masked with 0xfe equals 0xfc
        packed = addr.packed
        if packed[0] & 0xFE == 0xFC:  # noqa: PLR2004
            return True
    return False


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
        raise ConfigurationError(
            "Toxicity assessment is not enabled."
        )

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
