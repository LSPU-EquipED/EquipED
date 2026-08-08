"""Settings coverage for curriculum-alignment limiter controls."""

import pytest
from server.core.config import get_settings
from server.core.exceptions import ConfigurationError


def _clear_cached_settings() -> None:
    get_settings.cache_clear()


def test_curriculum_alignment_settings_default_values() -> None:
    _clear_cached_settings()
    settings = get_settings()

    assert settings.curriculum_alignment_max_concurrent_checks == 4
    assert settings.curriculum_alignment_max_checks_per_user == 1
    assert settings.curriculum_alignment_recheck_cooldown_seconds == 30


def test_curriculum_alignment_settings_are_env_overridable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_cached_settings()

    monkeypatch.setenv("CURRICULUM_ALIGNMENT_MAX_CONCURRENT_CHECKS", "6")
    monkeypatch.setenv("CURRICULUM_ALIGNMENT_MAX_CHECKS_PER_USER", "2")
    monkeypatch.setenv("CURRICULUM_ALIGNMENT_RECHECK_COOLDOWN_SECONDS", "45")
    _clear_cached_settings()

    settings = get_settings()
    assert settings.curriculum_alignment_max_concurrent_checks == 6
    assert settings.curriculum_alignment_max_checks_per_user == 2
    assert settings.curriculum_alignment_recheck_cooldown_seconds == 45


def test_curriculum_alignment_cross_field_validation_rejects_bad_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_cached_settings()

    monkeypatch.setenv("CURRICULUM_ALIGNMENT_MAX_CONCURRENT_CHECKS", "1")
    monkeypatch.setenv("CURRICULUM_ALIGNMENT_MAX_CHECKS_PER_USER", "2")
    _clear_cached_settings()

    with pytest.raises(ConfigurationError):
        get_settings()
