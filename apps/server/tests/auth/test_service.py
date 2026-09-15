"""Auth service layer tests."""

from __future__ import annotations

from server.core.config import Settings
from server.modules.auth.models import User, UserRole
from server.modules.auth.service import bootstrap_admin_if_configured
from sqlalchemy import select
from sqlalchemy.orm import Session


def test_bootstrap_admin_creates_first_admin(db_session: Session) -> None:
    settings = Settings(
        database_url=None,
        bootstrap_admin_email="bootstrap@lspu.edu.ph",
        bootstrap_admin_name="Bootstrap Admin",
        bootstrap_admin_password="correct-horse-battery",
    )

    created = bootstrap_admin_if_configured(db_session, settings)
    admin_user = db_session.scalar(
        select(User).where(User.email == "bootstrap@lspu.edu.ph")
    )

    assert created is True
    assert admin_user is not None
    assert admin_user.role == UserRole.ADMIN
