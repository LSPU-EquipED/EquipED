"""Config validation tests for auth and environment guards."""

import pytest
from server.core.config import get_settings
from server.core.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setenv("LLM_ALLOWED_ENDPOINTS", "")


def test_production_rejects_console_email_provider(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://equiped.lspu.edu.ph")
    get_settings.cache_clear()
    with pytest.raises(
        ConfigurationError, match="EMAIL_PROVIDER=console is not allowed in production"
    ):
        get_settings()


def test_production_rejects_insecure_session_cookie(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.lspu.edu.ph")
    monkeypatch.setenv("SMTP_USERNAME", "mailer")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_STARTTLS", "true")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://equiped.lspu.edu.ph")
    get_settings.cache_clear()
    with pytest.raises(
        ConfigurationError,
        match="SESSION_COOKIE_SECURE must be true outside development",
    ):
        get_settings()


def test_production_rejects_http_app_public_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.lspu.edu.ph")
    monkeypatch.setenv("SMTP_USERNAME", "mailer")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_STARTTLS", "true")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("APP_PUBLIC_URL", "http://equiped.lspu.edu.ph")
    get_settings.cache_clear()
    with pytest.raises(
        ConfigurationError, match="APP_PUBLIC_URL must use HTTPS outside development"
    ):
        get_settings()


def test_production_rejects_smtp_without_starttls(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.lspu.edu.ph")
    monkeypatch.setenv("SMTP_USERNAME", "mailer")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_STARTTLS", "false")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://equiped.lspu.edu.ph")
    get_settings.cache_clear()
    with pytest.raises(
        ConfigurationError, match="SMTP_STARTTLS must be true outside development"
    ):
        get_settings()


def test_development_allows_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("APP_PUBLIC_URL", "http://localhost:5173")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.environment == "development"
    assert settings.email_provider == "console"
    assert settings.session_cookie_secure is False
    assert settings.app_public_url == "http://localhost:5173"
