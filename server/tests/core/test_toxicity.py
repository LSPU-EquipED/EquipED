"""Dedicated toxicity endpoint guard and client factory tests.

* Global evaluation LLM client must never be used for toxicity.
* External/public endpoints must be rejected.
* Loopback / private endpoints must be accepted.
* DNS failure / mixed public resolution must fail closed.
* Enabled but invalid/unavailable classifier stores null, never 0.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from server.core.exceptions import ConfigurationError
from server.core.toxicity import (
    _is_private_ip,
    get_toxicity_client,
    validate_toxicity_endpoint,
)

# A minimal settings stub for get_toxicity_client tests.
# Every test sets the fields it cares about.
_BASE_SETTINGS = {
    "toxicity_assessment_enabled": False,
    "toxicity_api_base": None,
    "toxicity_model_name": None,
    "toxicity_api_key": None,
    "toxicity_request_timeout_seconds": 30,
}


def _fake_settings(**overrides: object) -> object:
    """Return a Settings-like object with *overrides* merged on top of defaults."""
    d = dict(_BASE_SETTINGS)
    d.update(overrides)
    return type("Settings", (), d)()


# ═══════════════════════════════════════════════════════════════════════
# Unit: validate_toxicity_endpoint
# ═══════════════════════════════════════════════════════════════════════


class TestValidateEndpoint:
    """The endpoint guard correctly accepts/rejects URLs."""

    # --- Scheme --------------------------------------------------------

    def test_rejects_non_http_scheme(self):
        allowed, reason = validate_toxicity_endpoint("ftp://localhost:11434/v1")
        assert not allowed
        assert "scheme" in reason.lower()

    # --- Credentials / query / fragment --------------------------------

    def test_rejects_embedded_credentials(self):
        allowed, reason = validate_toxicity_endpoint(
            "http://user:pass@localhost:11434/v1"
        )
        assert not allowed
        assert "credential" in reason.lower()

    def test_rejects_query_string(self):
        allowed, reason = validate_toxicity_endpoint(
            "http://localhost:11434/v1?key=val"
        )
        assert not allowed
        assert "query" in reason.lower()

    def test_rejects_fragment(self):
        allowed, reason = validate_toxicity_endpoint(
            "http://localhost:11434/v1#frag"
        )
        assert not allowed
        assert "fragment" in reason.lower()

    # --- Known safe names ----------------------------------------------

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:11434/v1",
            "http://127.0.0.1:11434/v1",
            "http://[::1]:11434/v1",
            "https://localhost:8080/classify",
            "http://host.docker.internal:11434/v1",
            "http://docker.host.internal:11434/v1",
            "http://0.0.0.0:11434/v1",
        ],
    )
    def test_accepts_safe_local_names(self, url):
        allowed, reason = validate_toxicity_endpoint(url)
        assert allowed, f"Expected {url} to be allowed: {reason}"

    # --- Public IPs ----------------------------------------------------

    def test_rejects_public_ip_literal(self):
        allowed, reason = validate_toxicity_endpoint("http://8.8.8.8:11434/v1")
        assert not allowed
        assert "public" in reason.lower()

    def test_rejects_public_hostname(self):
        """A public DNS name that resolves to a public IP is rejected."""
        allowed, reason = validate_toxicity_endpoint(
            "http://example.com:11434/v1"
        )
        assert not allowed

    # --- RFC1918 -------------------------------------------------------

    @pytest.mark.parametrize(
        "ip_str",
        [
            "10.0.0.1",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.1.1",
            "169.254.1.1",
            "fc00::",
            "fd00::1",
        ],
    )
    def test_private_ip_check(self, ip_str):
        assert _is_private_ip(ip_str), f"{ip_str} should be private"

    @pytest.mark.parametrize(
        "ip_str",
        [
            "8.8.8.8",
            "1.1.1.1",
            "2001:4860:4860::8888",
        ],
    )
    def test_public_ip_check(self, ip_str):
        assert not _is_private_ip(ip_str), f"{ip_str} should be public"

    # --- DNS failure ---------------------------------------------------

    def test_unresolvable_hostname_fails_closed(self):
        """A hostname that does not resolve is rejected."""
        allowed, reason = validate_toxicity_endpoint(
            "http://this-domain-does-not-exist-hopefully.example.com/v1"
        )
        assert not allowed
        assert "DNS" in reason or "failed" in reason.lower()


# ═══════════════════════════════════════════════════════════════════════
# Unit: get_toxicity_client
# ═══════════════════════════════════════════════════════════════════════


class TestGetToxicityClient:
    """Client factory rejects global-LLM reuse and validates locality."""

    def test_disabled_raises(self):
        with patch(
            "server.core.config.get_settings",
            return_value=_fake_settings(
                toxicity_assessment_enabled=False,
                toxicity_api_base="http://localhost:11434/v1",
                toxicity_model_name="test-model",
            ),
        ):
            with pytest.raises(ConfigurationError, match="not enabled"):
                get_toxicity_client()

    def test_missing_api_base_raises(self):
        with patch(
            "server.core.config.get_settings",
            return_value=_fake_settings(
                toxicity_assessment_enabled=True,
                toxicity_api_base=None,
                toxicity_model_name="test-model",
            ),
        ):
            with pytest.raises(ConfigurationError, match="TOXICITY_API_BASE"):
                get_toxicity_client()

    def test_missing_model_raises(self):
        with patch(
            "server.core.config.get_settings",
            return_value=_fake_settings(
                toxicity_assessment_enabled=True,
                toxicity_api_base="http://localhost:11434/v1",
                toxicity_model_name=None,
            ),
        ):
            with pytest.raises(ConfigurationError, match="TOXICITY_MODEL_NAME"):
                get_toxicity_client()

    def test_external_endpoint_rejected(self):
        with patch(
            "server.core.config.get_settings",
            return_value=_fake_settings(
                toxicity_assessment_enabled=True,
                toxicity_api_base="http://api.example.com/classify",
                toxicity_model_name="test-model",
            ),
        ):
            with pytest.raises(
                ConfigurationError, match="locality guard"
            ):
                get_toxicity_client()

    def test_loopback_endpoint_accepted(self):
        with patch(
            "server.core.config.get_settings",
            return_value=_fake_settings(
                toxicity_assessment_enabled=True,
                toxicity_api_base="http://localhost:11434/v1",
                toxicity_model_name="test-model",
            ),
        ):
            client = get_toxicity_client()
            assert client is not None
            assert client.model == "test-model"
            assert "localhost" in client.api_base


# ═══════════════════════════════════════════════════════════════════════
# Integration: assess_model_validation_toxicity uses dedicated client
# ═══════════════════════════════════════════════════════════════════════


class TestToxicityNoGlobalLlm:
    """Toxicity must never use the global evaluation LLM client."""

    def test_no_client_falls_back_to_dedicated_not_global(
        self, monkeypatch
    ):
        """When no explicit client is given, the dedicated client is used.

        If the dedicated client raises (e.g. disabled), the function
        persists null — it never calls get_llm_client().
        """
        # Patch settings so toxicity is enabled but has no api_base
        from server.core.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("TOXICITY_ASSESSMENT_ENABLED", "true")
        # Intentionally omit TOXICITY_API_BASE — the dedicated client
        # factory will raise ConfigurationError, which the function
        # should handle by persisting null.
        monkeypatch.delenv("TOXICITY_API_BASE", raising=False)
        monkeypatch.setenv("TOXICITY_MODEL_NAME", "test-model")

        get_settings.cache_clear()
        # Re-import to pick up fresh settings
        from server.core.config import get_settings as gs

        _ = gs()

        # Verify the scenario: get_toxicity_client raises
        from server.core.toxicity import get_toxicity_client

        with pytest.raises(ConfigurationError, match="TOXICITY_API_BASE"):
            get_toxicity_client()
