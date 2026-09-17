"""Shared fixtures for training_data module tests."""

from __future__ import annotations

from server.tests.admin.conftest import (  # noqa: F401 — re-exported fixtures
    admin_user,
    auth_cookies_admin,
    auth_cookies_faculty,
    faculty_user,
)
from server.tests.feedback.conftest import (  # noqa: F401 — re-exported fixtures
    evaluation_job,
)
