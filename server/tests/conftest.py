"""Test fixtures for server-side auth coverage."""

from __future__ import annotations

from collections.abc import Iterator
from importlib import import_module, reload

import pytest
from fastapi.testclient import TestClient
from server.core.config import Settings, get_settings
from server.core.database import Base, get_db_session
from server.db.metadata import import_model_modules
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        database_url=None,
        session_cookie_name="equiped_session",
        session_ttl_hours=24,
    )


@pytest.fixture()
def db_session() -> Iterator[Session]:
    import_model_modules()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    db_session: Session,
) -> Iterator[TestClient]:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_NAME", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()

    server_main = reload(import_module("server.main"))
    app = server_main.create_app()

    def override_get_db_session() -> Iterator[Session]:
        yield db_session

    def override_get_settings() -> Settings:
        return settings

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_settings] = override_get_settings

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
def seeded_user(db_session: Session):
    user = create_user(
        db_session,
        name="Platform Admin",
        email="admin@example.com",
        password="correct-horse-battery",
        role=UserRole.ADMIN,
    )
    db_session.commit()
    return user
