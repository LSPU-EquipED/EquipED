"""Email policy for locally managed EquipED accounts."""

from __future__ import annotations

import re

LSPU_EMAIL_DOMAIN = "@lspu.edu.ph"
MAX_EMAIL_LENGTH = 40
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_lspu_email(email: str) -> str:
    """Normalize and validate an official LSPU email address."""
    normalized = email.strip().lower()
    if len(normalized) > MAX_EMAIL_LENGTH:
        raise ValueError("Email must be 40 characters or fewer.")
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Enter a valid email address.")
    if not normalized.endswith(LSPU_EMAIL_DOMAIN):
        raise ValueError("Please use your official @lspu.edu.ph email address.")
    return normalized


__all__ = ["LSPU_EMAIL_DOMAIN", "MAX_EMAIL_LENGTH", "normalize_lspu_email"]
