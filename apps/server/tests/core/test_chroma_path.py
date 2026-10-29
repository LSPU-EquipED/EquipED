"""Tests for chroma path resolution regression."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from server.core import chroma
from server.core.config import _REPO_ROOT, Settings, _resolve_chroma_path, get_settings
from server.core.exceptions import ConfigurationError, InfrastructureUnavailableError


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


def test_default_test_client_cannot_select_deployment_cloud(monkeypatch, tmp_path):
    captured = []
    monkeypatch.setitem(
        __import__("sys").modules,
        "chromadb",
        SimpleNamespace(
            CloudClient=lambda **kwargs: pytest.fail("live cloud selected by test"),
            HttpClient=lambda **kwargs: pytest.fail("remote server selected by test"),
            PersistentClient=lambda **kwargs: captured.append(kwargs) or "isolated",
        ),
    )
    assert chroma.get_chroma_client() == "isolated"
    assert captured == [{"path": str(tmp_path / "chroma")}]


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


def test_cloud_settings_are_loaded_and_api_key_is_hidden(monkeypatch) -> None:
    _clear_settings_cache_and_pin_budgets(monkeypatch)
    monkeypatch.setenv("CHROMA_API_KEY", "private-key")
    monkeypatch.setenv("CHROMA_TENANT", "tenant")
    monkeypatch.setenv("CHROMA_DATABASE", "database")
    try:
        settings = get_settings()
        assert settings.chroma_api_key == "private-key"
        assert settings.chroma_tenant == "tenant"
        assert settings.chroma_database == "database"
        assert "private-key" not in repr(settings)
    finally:
        get_settings.cache_clear()


def test_cloud_client_selected_with_explicit_credentials(monkeypatch) -> None:
    calls = []
    fake = SimpleNamespace(
        CloudClient=lambda **kwargs: calls.append(("cloud", kwargs)) or "cloud-client",
        HttpClient=lambda **kwargs: pytest.fail("unexpected HttpClient"),
        PersistentClient=lambda **kwargs: pytest.fail("unexpected PersistentClient"),
    )
    monkeypatch.setattr(
        chroma,
        "get_settings",
        lambda: Settings(
            chroma_api_key="secret",
            chroma_tenant="tenant",
            chroma_database="database",
        ),
    )
    monkeypatch.setitem(__import__("sys").modules, "chromadb", fake)
    chroma.get_chroma_client.cache_clear()
    try:
        assert chroma.get_chroma_client() == "cloud-client"
        assert calls == [
            (
                "cloud",
                {
                    "api_key": "secret",
                    "tenant": "tenant",
                    "database": "database",
                },
            )
        ]
    finally:
        chroma.get_chroma_client.cache_clear()


@pytest.mark.parametrize(
    "values",
    [
        {"chroma_api_key": "secret"},
        {"chroma_tenant": "tenant", "chroma_database": "database"},
        {"chroma_host": "api.trychroma.com", "chroma_api_key": "secret"},
        {"chroma_host": "api.trychroma.com"},
    ],
)
def test_incomplete_cloud_configuration_fails_closed(monkeypatch, values) -> None:
    monkeypatch.setattr(chroma, "get_settings", lambda: Settings(**values))
    chroma.get_chroma_client.cache_clear()
    try:
        with pytest.raises(ConfigurationError):
            chroma.get_chroma_client()
    finally:
        chroma.get_chroma_client.cache_clear()


def test_cloud_host_with_noncanonical_host_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        chroma,
        "get_settings",
        lambda: Settings(
            chroma_host="custom.example.com",
            chroma_api_key="secret",
            chroma_tenant="tenant",
            chroma_database="database",
        ),
    )
    chroma.get_chroma_client.cache_clear()
    try:
        with pytest.raises(ConfigurationError):
            chroma.get_chroma_client()
    finally:
        chroma.get_chroma_client.cache_clear()


def test_chroma_configured_recognizes_complete_cloud_config() -> None:
    settings = Settings(
        chroma_host="api.trychroma.com",
        chroma_api_key="secret",
        chroma_tenant="tenant",
        chroma_database="database",
    )
    assert settings.chroma_configured is True


def test_chroma_configured_rejects_incomplete_cloud_config() -> None:
    settings = Settings(chroma_host="api.trychroma.com", chroma_api_key="secret")
    assert settings.chroma_configured is False


def test_cloud_initialization_error_does_not_expose_credentials(monkeypatch) -> None:
    secret = "do-not-leak"

    def fail(**kwargs):
        raise RuntimeError(f"request failed with {kwargs['api_key']}")

    monkeypatch.setattr(
        chroma,
        "get_settings",
        lambda: Settings(
            chroma_api_key=secret,
            chroma_tenant="tenant",
            chroma_database="database",
        ),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "chromadb",
        SimpleNamespace(
            CloudClient=fail,
        ),
    )
    chroma.get_chroma_client.cache_clear()
    try:
        with pytest.raises(InfrastructureUnavailableError) as error:
            chroma.get_chroma_client()
        assert secret not in str(error.value)
        assert error.value.__cause__ is None
        assert error.value.__context__ is None
    finally:
        chroma.get_chroma_client.cache_clear()


@pytest.mark.parametrize(
    "settings, expected",
    [
        (
            Settings(chroma_host="localhost", chroma_port=8000),
            ("http", {"host": "localhost", "port": 8000, "ssl": False}),
        ),
        (
            Settings(chroma_host=None),
            ("persistent", {"path": Settings().chroma_persist_directory}),
        ),
    ],
)
def test_non_cloud_client_modes_remain_compatible(
    monkeypatch, settings, expected
) -> None:
    calls = []
    fake = SimpleNamespace(
        CloudClient=lambda **kwargs: pytest.fail("unexpected CloudClient"),
        HttpClient=lambda **kwargs: calls.append(("http", kwargs)) or "client",
        PersistentClient=lambda **kwargs: (
            calls.append(("persistent", kwargs)) or "client"
        ),
    )
    monkeypatch.setattr(chroma, "get_settings", lambda: settings)
    monkeypatch.setitem(__import__("sys").modules, "chromadb", fake)
    chroma.get_chroma_client.cache_clear()
    try:
        assert chroma.get_chroma_client() == "client"
        assert calls == [expected]
    finally:
        chroma.get_chroma_client.cache_clear()
