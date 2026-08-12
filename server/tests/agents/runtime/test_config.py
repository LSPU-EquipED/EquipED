"""Tests for config validation of agent packing settings."""

from __future__ import annotations

import pytest
from server.core.config import get_settings
from server.core.exceptions import ConfigurationError


def _clear_settings_cache(monkeypatch) -> None:
    """Clear the lru_cache so each test gets a fresh parse.

    NOTE: We pin ``AGENT_PROMPT_BUDGET_CHARS`` to a value strictly less
    than the new ``AGENT_TOTAL_PROMPT_BUDGET_CHARS`` default (8000).
    Otherwise the cross-field validation in ``get_settings()`` would fire
    on every test that calls it (the dataclass default 5000 is no
    longer compatible with the new 8000 total budget). Individual tests
    that want to exercise the chunk budget in isolation still override
    this via ``monkeypatch.setenv(..., "<value>")`` after the helper
    runs.
    """
    from server.core import config as _config_mod

    _config_mod.get_settings.cache_clear()
    monkeypatch.setenv("AGENT_MAX_CHUNKS", "")
    monkeypatch.setenv("AGENT_MAX_EXCERPT_CHARS", "")
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")
    monkeypatch.setenv("AGENT_SMALL_DOC_THRESHOLD", "")
    monkeypatch.setenv("AGENT_TOTAL_PROMPT_BUDGET_CHARS", "")


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


# ------------------------------------------------------------------
# Total-prompt budget (safety net for remote LLM providers)
# ------------------------------------------------------------------


def test_config_default_total_prompt_budget_is_8000(monkeypatch) -> None:
    """AGENT_TOTAL_PROMPT_BUDGET_CHARS should default to 8000 to keep
    assembled prompts safely below the Groq free-tier 6,000 TPM cap.
    With dense rubric text (~1.6 chars/token), 8000 chars ≈ 5000 input
    tokens, well under the 6000 TPM limit even with 4096 output tokens."""
    _clear_settings_cache(monkeypatch)
    try:
        settings = get_settings()
        assert settings.agent_total_prompt_budget_chars == 8000
    finally:
        get_settings.cache_clear()


def test_config_accepts_total_prompt_budget_override(monkeypatch) -> None:
    """AGENT_TOTAL_PROMPT_BUDGET_CHARS env override should take effect."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_TOTAL_PROMPT_BUDGET_CHARS", "50000")
    try:
        settings = get_settings()
        assert settings.agent_total_prompt_budget_chars == 50000
    finally:
        get_settings.cache_clear()


def test_config_rejects_tiny_total_prompt_budget(monkeypatch) -> None:
    """AGENT_TOTAL_PROMPT_BUDGET_CHARS below 1000 should raise ConfigurationError."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_TOTAL_PROMPT_BUDGET_CHARS", "500")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "AGENT_TOTAL_PROMPT_BUDGET_CHARS must be at least 1000" in str(exc)
    finally:
        get_settings.cache_clear()


def test_config_rejects_non_integer_total_prompt_budget(monkeypatch) -> None:
    """Non-integer AGENT_TOTAL_PROMPT_BUDGET_CHARS should raise ConfigurationError."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_TOTAL_PROMPT_BUDGET_CHARS", "not-a-number")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "AGENT_TOTAL_PROMPT_BUDGET_CHARS must be a valid integer" in str(exc)
    finally:
        get_settings.cache_clear()


# ------------------------------------------------------------------
# Cross-field validation: chunk budget must be less than total budget
# ------------------------------------------------------------------


def test_config_rejects_chunk_budget_equal_to_total(monkeypatch) -> None:
    """AGENT_PROMPT_BUDGET_CHARS == AGENT_TOTAL_PROMPT_BUDGET_CHARS should
    raise ConfigurationError — they must be strictly ordered so the total
    budget safety net has headroom over the chunk budget."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")
    monkeypatch.setenv("AGENT_TOTAL_PROMPT_BUDGET_CHARS", "5000")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "AGENT_PROMPT_BUDGET_CHARS must be less than" in str(exc)
        assert "AGENT_TOTAL_PROMPT_BUDGET_CHARS" in str(exc)
    finally:
        get_settings.cache_clear()


def test_config_rejects_chunk_budget_greater_than_total(monkeypatch) -> None:
    """AGENT_PROMPT_BUDGET_CHARS > AGENT_TOTAL_PROMPT_BUDGET_CHARS should
    raise ConfigurationError. If the chunk budget already exceeds the
    total budget, the document_chunks payload alone would blow past the
    safety net and the trim loop in _enforce_total_prompt_budget would
    fire on every single run."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "9000")
    monkeypatch.setenv("AGENT_TOTAL_PROMPT_BUDGET_CHARS", "8000")
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "AGENT_PROMPT_BUDGET_CHARS must be less than" in str(exc)
    finally:
        get_settings.cache_clear()


def test_config_accepts_chunk_budget_strictly_less_than_total(
    monkeypatch,
) -> None:
    """AGENT_PROMPT_BUDGET_CHARS < AGENT_TOTAL_PROMPT_BUDGET_CHARS should
    parse without error — the safety net has room to operate."""
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "2000")
    monkeypatch.setenv("AGENT_TOTAL_PROMPT_BUDGET_CHARS", "5000")
    try:
        settings = get_settings()
        assert settings.agent_prompt_budget_chars == 2000
        assert settings.agent_total_prompt_budget_chars == 5000
    finally:
        get_settings.cache_clear()


def test_config_default_sme_total_prompt_budget_is_15000(monkeypatch) -> None:
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("SME_TOTAL_PROMPT_BUDGET_CHARS", "")
    try:
        assert get_settings().sme_total_prompt_budget_chars == 15000
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("value", ["not-a-number", "14999"])
def test_config_rejects_invalid_sme_total_prompt_budget(monkeypatch, value) -> None:
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("SME_TOTAL_PROMPT_BUDGET_CHARS", value)
    try:
        with pytest.raises(ConfigurationError, match="SME_TOTAL_PROMPT_BUDGET_CHARS"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_config_accepts_minimum_sme_total_prompt_budget(monkeypatch) -> None:
    _clear_settings_cache(monkeypatch)
    monkeypatch.setenv("SME_TOTAL_PROMPT_BUDGET_CHARS", "15000")
    try:
        assert get_settings().sme_total_prompt_budget_chars == 15000
    finally:
        get_settings.cache_clear()
