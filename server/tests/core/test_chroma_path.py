"""Tests for chroma path resolution regression."""

from __future__ import annotations

import pytest

from server.core.config import Settings, _REPO_ROOT, _resolve_chroma_path, get_settings


def _clear_settings_cache_and_pin_budgets(monkeypatch) -> None:
    """Clear the lru_cache and pin the prompt budgets so the cross-field
    validation does not fire on default settings. The two failing
    tests below set only ``CHROMA_PERSIST_DIRECTORY``; with the new
    8,000-char total budget default, an unpinned 5,000-char chunk
    budget would trip the validation."""
    from server.core import config as _config_mod
    _config_mod.get_settings.cache_clear()
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")
    monkeypatch.setenv("AGENT_TOTAL_PROMPT_BUDGET_CHARS", "")


def test_chroma_path_resolver_relative_anchors_to_repo_root() -> None:
    """Relative chroma paths must resolve against repo root, not CWD."""
    result = _resolve_chroma_path("chroma_data")
    assert result == str(_REPO_ROOT / "chroma_data")
    # Must NOT contain "server/chroma_data"
    assert "server" not in result.split("/")[-2:]


def test_chroma_path_resolver_preserves_absolute_paths() -> None:
    """Absolute chroma paths must be preserved as-is."""
    abs_path = "/tmp/custom_chroma"
    result = _resolve_chroma_path(abs_path)
    assert result == abs_path


def test_chroma_path_resolver_handles_nested_relative() -> None:
    """Nested relative paths should also resolve against repo root."""
    result = _resolve_chroma_path("data/vectors/chroma")
    assert result == str(_REPO_ROOT / "data" / "vectors" / "chroma")


def test_settings_chroma_default_is_repo_root_path(monkeypatch) -> None:
    """Default Settings chroma_persist_directory should point to repo root."""
    settings = Settings()
    expected = str(_REPO_ROOT / "chroma_data")
    assert settings.chroma_persist_directory == expected


def test_settings_chroma_env_var_resolves_relative(monkeypatch) -> None:
    """CHROMA_PERSIST_DIRECTORY env var with relative path resolves to repo root."""
    _clear_settings_cache_and_pin_budgets(monkeypatch)
    monkeypatch.setenv("CHROMA_PERSIST_DIRECTORY", "my_chroma")
    try:
        settings = get_settings()
        assert settings.chroma_persist_directory.endswith("my_chroma")
        assert "server" not in settings.chroma_persist_directory.split("/")[-3:]
    finally:
        get_settings.cache_clear()


def test_settings_chroma_env_var_preserves_absolute(monkeypatch) -> None:
    """CHROMA_PERSIST_DIRECTORY env var with absolute path is preserved."""
    _clear_settings_cache_and_pin_budgets(monkeypatch)
    monkeypatch.setenv("CHROMA_PERSIST_DIRECTORY", "/opt/equiped/chroma")
    try:
        settings = get_settings()
        assert settings.chroma_persist_directory == "/opt/equiped/chroma"
    finally:
        get_settings.cache_clear()
