"""Transactional authentication email delivery tests."""

import smtplib

import pytest
from server.core.config import Settings
from server.modules.auth import email as email_module


class FakeSMTP:
    instance = None

    def __init__(self, host, port, *, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.ehlo_calls = 0
        self.starttls_context = None
        self.credentials = None
        self.message = None
        type(self).instance = self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def ehlo(self):
        self.ehlo_calls += 1

    def starttls(self, *, context):
        self.starttls_context = context

    def login(self, username, password):
        self.credentials = (username, password)

    def send_message(self, message):
        self.message = message


def smtp_settings(**overrides) -> Settings:
    values = {
        "email_provider": "smtp",
        "email_from": "EquipED <equipedlspu@gmail.com>",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_username": "equipedlspu@gmail.com",
        "smtp_password": "app-password",
        "smtp_starttls": True,
        "smtp_timeout_seconds": 10,
    }
    values.update(overrides)
    return Settings(**values)


def test_smtp_delivery_uses_starttls_and_app_credentials(monkeypatch):
    monkeypatch.setattr(email_module.smtplib, "SMTP", FakeSMTP)

    email_module.send_email(
        settings=smtp_settings(),
        to="faculty@lspu.edu.ph",
        subject="Your EquipED verification code",
        text="Your code is 123456.",
    )

    smtp = FakeSMTP.instance
    assert smtp.host == "smtp.gmail.com"
    assert smtp.port == 587
    assert smtp.timeout == 10
    assert smtp.ehlo_calls == 2
    assert smtp.starttls_context is not None
    assert smtp.credentials == ("equipedlspu@gmail.com", "app-password")
    assert smtp.message["From"] == "EquipED <equipedlspu@gmail.com>"
    assert smtp.message["To"] == "faculty@lspu.edu.ph"
    assert smtp.message.get_content().strip() == "Your code is 123456."


def test_smtp_delivery_requires_complete_configuration():
    with pytest.raises(RuntimeError, match="SMTP email delivery is not configured"):
        email_module.send_email(
            settings=smtp_settings(smtp_password=None),
            to="faculty@lspu.edu.ph",
            subject="OTP",
            text="Code",
        )


def test_smtp_transport_errors_are_sanitized(monkeypatch):
    class FailingSMTP(FakeSMTP):
        def login(self, username, password):
            raise smtplib.SMTPAuthenticationError(535, b"Authentication failed")

    monkeypatch.setattr(email_module.smtplib, "SMTP", FailingSMTP)

    with pytest.raises(RuntimeError, match="SMTP email delivery failed"):
        email_module.send_email(
            settings=smtp_settings(),
            to="faculty@lspu.edu.ph",
            subject="OTP",
            text="Code",
        )
