"""Tests for config validation of agent packing settings."""

from __future__ import annotations

import pytest

from server.core.config import get_settings
from server.core.exceptions import ConfigurationError


def _clear_settings_cache(monkeypatch) -> None:
    """Clear the lru_cache so each test gets a fresh parse."""
    from server.core import config as _config_mod
    _config_mod.get_settings.cache_clear()
    monkeypatch.setenv("AGENT_MAX_CHUNKS", "")
    monkeypatch.setenv("AGENT_MAX_EXCERPT_CHARS", "")
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "")
    monkeypatch.setenv("AGENT_SMALL_DOC_THRESHOLD", "")


def test_config_rejects_zero_max_chunks(monkeypatch) -> None:
    """AGENT_MAX_CHUNKS=0 should raise ConfigurationError."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_MAX_CHUNKS", "0")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "AGENT_MAX_CHUNKS must be at least 1" in str(exc)
    finally:
        get_settings.cache_clear()


def test_config_rejects_negative_excerpt_chars(monkeypatch) -> None:
    """AGENT_MAX_EXCERPT_CHARS below 50 should raise ConfigurationError."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_MAX_EXCERPT_CHARS", "10")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "AGENT_MAX_EXCERPT_CHARS must be at least 50" in str(exc)
    finally:
        get_settings.cache_clear()


def test_config_rejects_tiny_budget(monkeypatch) -> None:
    """AGENT_PROMPT_BUDGET_CHARS below 200 should raise ConfigurationError."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "50")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "AGENT_PROMPT_BUDGET_CHARS must be at least 200" in str(exc)
    finally:
        get_settings.cache_clear()


def test_config_rejects_zero_small_doc_threshold(monkeypatch) -> None:
    """AGENT_SMALL_DOC_THRESHOLD=0 should raise ConfigurationError."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_SMALL_DOC_THRESHOLD", "0")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "AGENT_SMALL_DOC_THRESHOLD must be at least 1" in str(exc)
    finally:
        get_settings.cache_clear()


def test_config_accepts_valid_bounds(monkeypatch) -> None:
    """Valid env values within bounds should parse without error."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_MAX_CHUNKS", "5")
    monkeypatch.setenv("AGENT_MAX_EXCERPT_CHARS", "100")
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "500")
    monkeypatch.setenv("AGENT_SMALL_DOC_THRESHOLD", "3")
    try:
        settings = get_settings()
        assert settings.agent_max_chunks == 5
        assert settings.agent_max_excerpt_chars == 100
        assert settings.agent_prompt_budget_chars == 500
        assert settings.agent_small_doc_threshold == 3
    finally:
        get_settings.cache_clear()


def test_config_default_llm_max_new_tokens_is_4096(monkeypatch) -> None:
    """The LLM generation budget should default to 4096 to give larger
    SLM evaluation outputs more headroom and reduce JSON truncation."""
    _clear_settings_cache(monkeypatch)
    # Set to empty string (not delenv) so load_dotenv() will not re-load
    # the .env override during get_settings() and the dataclass default
    # of 4096 takes effect.
    monkeypatch.setenv("LLM_MAX_NEW_TOKENS", "")
    try:
        settings = get_settings()
        assert settings.llm_max_new_tokens == 4096
    finally:
        get_settings.cache_clear()


def test_config_rejects_zero_llm_max_new_tokens(monkeypatch) -> None:
    """LLM_MAX_NEW_TOKENS=0 should raise ConfigurationError."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("LLM_MAX_NEW_TOKENS", "0")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "LLM_MAX_NEW_TOKENS must be at least 1" in str(exc)
    finally:
        get_settings.cache_clear()
