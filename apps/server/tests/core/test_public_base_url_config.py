"""Config validation for PUBLIC_BASE_URL (the address handed to Colab)."""

import pytest
from server.core.config import get_settings
from server.core.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setenv("LLM_ALLOWED_ENDPOINTS", "")
    # Empty, not deleted: get_settings() loads the repo .env, which may define it,
    # and load_dotenv never overrides a variable that already exists.
    monkeypatch.setenv("PUBLIC_BASE_URL", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_public_base_url_defaults_to_none():
    assert get_settings().public_base_url is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://abc.trycloudflare.com", "https://abc.trycloudflare.com"),
        ("https://abc.trycloudflare.com/", "https://abc.trycloudflare.com"),
        ("  https://abc.example.org  ", "https://abc.example.org"),
        ("http://192.168.1.20:8000", "http://192.168.1.20:8000"),
    ],
)
def test_public_base_url_is_normalized(monkeypatch, raw, expected):
    monkeypatch.setenv("PUBLIC_BASE_URL", raw)
    get_settings.cache_clear()
    assert get_settings().public_base_url == expected


@pytest.mark.parametrize(
    "raw",
    [
        "abc.trycloudflare.com",  # no scheme
        "ftp://abc.example.org",  # wrong scheme
        "https://",  # no host
        "https://user:pw@abc.example.org",  # credentials
        "https://abc.example.org/api/v1",  # path (the app adds API_PREFIX itself)
        "https://abc.example.org?x=1",  # query
        "https://abc.example.org#frag",  # fragment
    ],
)
def test_public_base_url_rejects_unusable_values(monkeypatch, raw):
    monkeypatch.setenv("PUBLIC_BASE_URL", raw)
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError, match="PUBLIC_BASE_URL"):
        get_settings()
