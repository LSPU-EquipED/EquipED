"""Transactional email delivery for authentication workflows."""

from __future__ import annotations

import json
import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.request import Request, urlopen

from server.core.config import Settings

logger = logging.getLogger(__name__)


def _send_smtp(*, settings: Settings, to: str, subject: str, text: str) -> None:
    if (
        not settings.smtp_host
        or not settings.smtp_username
        or not settings.smtp_password
    ):
        raise RuntimeError("SMTP email delivery is not configured")

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as smtp:
            smtp.ehlo()
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise RuntimeError("SMTP email delivery failed") from exc


def send_email(*, settings: Settings, to: str, subject: str, text: str) -> None:
    if settings.email_provider == "console":
        logger.info("Authentication email to %s: %s\n%s", to, subject, text)
        return
    if settings.email_provider == "smtp":
        _send_smtp(settings=settings, to=to, subject=subject, text=text)
        return
    if settings.email_provider != "resend" or not settings.resend_api_key:
        raise RuntimeError("Email delivery is not configured")

    payload = json.dumps(
        {"from": settings.email_from, "to": [to], "subject": subject, "text": text}
    ).encode()
    request = Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "EquipED/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed provider URL
        if response.status >= 300:
            raise RuntimeError(f"Email provider returned status {response.status}")


def send_otp_email(*, settings: Settings, to: str, name: str, otp: str) -> None:
    send_email(
        settings=settings,
        to=to,
        subject="Your EquipED verification code",
        text=(
            f"Hello {name},\n\nYour EquipED verification code is {otp}. "
            "It expires in 10 minutes.\n\nIf you did not request an account, "
            "you can ignore this email."
        ),
    )


def send_status_email(
    *, settings: Settings, to: str, name: str, approved: bool
) -> None:
    if approved:
        text = (
            f"Hello {name},\n\nYour EquipED account has been approved. "
            f"You may now sign in at {settings.app_public_url}/login using your "
            "registered LSPU email and password."
        )
        subject = "Your EquipED account was approved"
    else:
        text = (
            f"Hello {name},\n\nYour EquipED account registration was not "
            "approved at this time. Please contact your LSPU administrator or "
            "resubmit your registration with updated information."
        )
        subject = "Update about your EquipED account"
    send_email(settings=settings, to=to, subject=subject, text=text)
