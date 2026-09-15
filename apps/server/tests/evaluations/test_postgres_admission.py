"""Opt-in PostgreSQL concurrency characterization for admission FIFO.

Run only against a disposable database, for example:
``POSTGRES_TEST_DISPOSABLE=YES POSTGRES_TEST_DATABASE_URL=... pytest ...``.
"""

from __future__ import annotations

import os
import sys
import threading
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.modules.evaluations.service import (  # noqa: E402
    acquire_next_evaluation_execution,
)


def _postgres_target(url_string: str) -> tuple[str, str, int, str, str]:
    url = make_url(url_string)
    dialect = url.drivername.split("+", 1)[0].lower()
    if dialect != "postgresql":
        raise ValueError("not a PostgreSQL URL")
    return (
        dialect,
        (url.host or "").lower(),
        url.port or 5432,
        url.database or "",
        url.username or "",
    )


def _require_disposable_postgres(url: str) -> None:
    if os.environ.get("POSTGRES_TEST_DISPOSABLE", "").strip().upper() != "YES":
        pytest.skip("POSTGRES_TEST_DISPOSABLE=YES is required for PostgreSQL tests")
    try:
        target = _postgres_target(url)
    except (ValueError, TypeError) as exc:
        pytest.skip(f"POSTGRES_TEST_DATABASE_URL is not PostgreSQL: {exc}")
    configured = os.environ.get("DATABASE_URL", "").strip()
    if configured:
        try:
            same_target = target == _postgres_target(configured)
        except (ValueError, TypeError):
            same_target = False
        if same_target:
            pytest.fail(
                "refusing PostgreSQL test: test and application URLs target the "
                "same database"
            )


@pytest.mark.parametrize(
    ("test_url", "configured_url"),
    [
        (
            "postgresql://user%40name:pw@LOCALHOST/db",
            "postgresql+psycopg://user%40name:pw@localhost:5432/db?a=1&b=2",
        ),
    ],
)
def test_postgres_target_rejects_equivalent_urls(monkeypatch, test_url, configured_url):
    monkeypatch.setenv("POSTGRES_TEST_DISPOSABLE", "YES")
    monkeypatch.setenv("DATABASE_URL", configured_url)
    with pytest.raises(pytest.fail.Exception, match="same database"):
        _require_disposable_postgres(test_url)


def test_postgres_admission_is_single_claimant_and_fifo():
    url = os.environ.get("POSTGRES_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not set")
    _require_disposable_postgres(url)
    engine = create_engine(url, pool_size=5, max_overflow=0)
    assert "admission_slot" in {
        c["name"] for c in inspect(engine).get_columns("evaluation_jobs")
    }
    with engine.begin() as conn:
        doc = conn.execute(
            text("SELECT document_id FROM documents LIMIT 1")
        ).scalar_one_or_none()
    if doc is None:
        pytest.skip("migrated PostgreSQL schema has no document fixture")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    ids = []
    try:
        with engine.begin() as conn:
            if conn.execute(
                text("SELECT count(*) FROM evaluation_jobs WHERE admission_slot = 1")
            ).scalar_one():
                pytest.skip(
                    "pre-existing evaluation job already occupies admission_slot=1"
                )
            oldest = conn.execute(
                text(
                    "SELECT min(submitted_at) FROM evaluation_jobs "
                    "WHERE status = 'SUBMITTED'"
                )
            ).scalar_one()
            if oldest is not None and oldest <= datetime(1970, 1, 2, tzinfo=UTC):
                pytest.skip(
                    "cannot safely choose an earlier bounded synthetic timestamp"
                )
            base = (oldest - timedelta(days=1)) if oldest else datetime.now(UTC)
        for round_no in range(5):
            old, new = uuid4(), uuid4()
            ids.extend((old, new))
            with engine.begin() as conn:
                round_base = base + timedelta(seconds=round_no)
                for ident, submitted in (
                    (old, round_base),
                    (new, round_base + timedelta(seconds=1)),
                ):
                    conn.execute(
                        text(
                            "INSERT INTO evaluation_jobs (evaluation_id, document_id, "
                            "status, submitted_at) VALUES (:id, :doc, 'SUBMITTED', :at)"
                        ),
                        {"id": ident, "doc": doc, "at": submitted},
                    )
            barrier = threading.Barrier(2)
            results = []
            errors = []
            results_lock = threading.Lock()

            def claim():
                db = factory()
                try:
                    barrier.wait(timeout=10)
                    result = acquire_next_evaluation_execution(db, uuid4())
                    with results_lock:
                        results.append(result)
                except BaseException as exc:
                    with results_lock:
                        errors.append(exc)
                finally:
                    db.close()

            threads = [threading.Thread(target=claim) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
                assert not t.is_alive()
            assert not errors
            assert sorted(x for x in results if x) == [old]
            assert len(results) == 2
            with engine.begin() as conn:
                assert (
                    conn.execute(
                        text(
                            "SELECT count(*) FROM evaluation_jobs "
                            "WHERE admission_slot = 1"
                        )
                    ).scalar_one()
                    == 1
                )
                conn.execute(
                    text(
                        "DELETE FROM evaluation_jobs "
                        "WHERE evaluation_id IN (:old, :new)"
                    ),
                    {"old": old, "new": new},
                )
                assert (
                    conn.execute(
                        text(
                            "SELECT count(*) FROM evaluation_jobs "
                            "WHERE admission_slot = 1"
                        )
                    ).scalar_one()
                    == 0
                )
    finally:
        with engine.begin() as conn:
            for ident in ids:
                conn.execute(
                    text("DELETE FROM evaluation_jobs WHERE evaluation_id = :id"),
                    {"id": ident},
                )
        engine.dispose()
