"""Tests for the managed account email policy."""

from __future__ import annotations

import pytest

from server.modules.auth.email_policy import normalize_lspu_email


def test_normalize_lspu_email_trims_and_lowercases() -> None:
    assert normalize_lspu_email("  Faculty@LSPU.EDU.PH ") == "faculty@lspu.edu.ph"


@pytest.mark.parametrize(
    "email",
    [
        "faculty@example.com",
        "faculty@lspu.edu.ph.evil.test",
        "invalid email@lspu.edu.ph",
        "a" * 29 + "@lspu.edu.ph",
    ],
)
def test_normalize_lspu_email_rejects_invalid_addresses(email: str) -> None:
    with pytest.raises(ValueError):
        normalize_lspu_email(email)
