"""Characterization tests for the process-local evaluation queue."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from server.core.database import Base
from server.db.metadata import import_model_modules
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import (
    drain_evaluation_queue,
    recover_interrupted_evaluation_jobs,
)
from server.modules.evaluations.service import (
    acquire_next_evaluation_execution,
    heartbeat_evaluation_execution,
    seconds_until_stale_evaluation_execution,
)
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from .test_execution_ownership import _make_job, _make_session_factory


def _file_session_factory(path):
    import_model_modules()
    engine = create_engine(
        f"sqlite+pysqlite:///{path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _active_job(session, *, status, submitted_at, heartbeat, token=None):
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        submitted_by=uuid4(),
        status=status.value,
        submitted_at=submitted_at,
        execution_token=token,
        execution_started_at=submitted_at,
        execution_heartbeat_at=heartbeat,
        admission_slot=1,
    )
    session.add(job)
    session.commit()
    return job


def test_sqlite_naive_heartbeat_has_finite_wait(tmp_path) -> None:
    factory = _file_session_factory(tmp_path / "naive.db")
    session = factory()
    try:
        job = _active_job(
            session,
            status=EvaluationStatus.PREPROCESSING,
            submitted_at=datetime.now(UTC),
            heartbeat=datetime.now(UTC).replace(tzinfo=None),
            token=uuid4(),
        )
        seconds = seconds_until_stale_evaluation_execution(session, 0.05)
        assert seconds is not None
        assert 0 <= seconds <= 0.05
        assert job.execution_heartbeat_at is not None
    finally:
        session.close()


@pytest.mark.parametrize("attempt", range(5))
def test_drain_recovers_stale_slot_and_runs_fifo_once(
    tmp_path, monkeypatch, attempt
) -> None:
    factory = _file_session_factory(tmp_path / f"queue-{attempt}.db")
    now = datetime.now(UTC).replace(tzinfo=None)
    session = factory()
    lease = _active_job(
        session,
        status=EvaluationStatus.PREPROCESSING,
        submitted_at=now,
        heartbeat=now,
        token=uuid4(),
    )
    queued = _make_job(session)
    queued.submitted_at = now - timedelta(seconds=3)
    queued_id, lease_id = queued.evaluation_id, lease.evaluation_id
    session.commit()
    session.close()
    monkeypatch.setattr(
        "server.core.config.get_settings",
        lambda: type("S", (), {"evaluation_heartbeat_stale_seconds": 0.3})(),
    )
    calls = []
    entered = threading.Event()

    def execute(evaluation_id, *, db_session_factory, execution_token):
        entered.set()
        calls.append(evaluation_id)
        db = db_session_factory()
        try:
            db.execute(
                update(EvaluationJob)
                .where(
                    EvaluationJob.evaluation_id == evaluation_id,
                    EvaluationJob.execution_token == execution_token,
                )
                .values(
                    status=EvaluationStatus.COMPLETED.value,
                    admission_slot=None,
                    execution_token=None,
                )
            )
            db.commit()
        finally:
            db.close()

    monkeypatch.setattr(
        "server.modules.evaluations.orchestrator._execute_claimed_evaluation", execute
    )

    class LeaseWait:
        def __init__(self):
            self.entered = threading.Event()
            self.release = threading.Event()

        def is_set(self):
            return False

        def wait(self, timeout=None):
            self.entered.set()
            self.release.wait(timeout)
            return False

    lease_wait = LeaseWait()
    thread = threading.Thread(
        target=drain_evaluation_queue,
        args=(factory,),
        kwargs={"stop_event": lease_wait},
    )
    thread.start()
    assert lease_wait.entered.wait(1)
    assert calls == []
    # Keep the drainer in its lease wait until the configured lease has
    # expired.  This observes the pre-expiry state without racing a wall-clock
    # assertion against the scheduler.
    time.sleep(0.45)
    lease_wait.release.set()
    assert entered.wait(2)
    thread.join(2)
    assert not thread.is_alive()
    assert calls == [queued_id, lease_id]
    db = factory()
    try:
        rows = [db.get(EvaluationJob, item) for item in calls]
        assert all(row.status == EvaluationStatus.COMPLETED.value for row in rows)
        assert all(
            row.admission_slot is None and row.execution_token is None for row in rows
        )
    finally:
        db.close()


def test_drain_heartbeat_extension_delays_recovery(tmp_path, monkeypatch) -> None:
    factory = _file_session_factory(tmp_path / "heartbeat.db")
    stale_seconds = 0.9
    session = factory()
    heartbeat_time = datetime.now(UTC)
    job = _active_job(
        session,
        status=EvaluationStatus.PREPROCESSING,
        submitted_at=heartbeat_time - timedelta(seconds=1),
        heartbeat=heartbeat_time,
        token=uuid4(),
    )
    token = job.execution_token
    job_id = job.evaluation_id
    session.close()
    original_expiry = time.monotonic() + stale_seconds
    monkeypatch.setattr(
        "server.core.config.get_settings",
        lambda: type("S", (), {"evaluation_heartbeat_stale_seconds": stale_seconds})(),
    )
    calls = []

    def execute(evaluation_id, *, db_session_factory, execution_token):
        calls.append(evaluation_id)
        db = db_session_factory()
        db.execute(
            update(EvaluationJob)
            .where(
                EvaluationJob.evaluation_id == evaluation_id,
                EvaluationJob.execution_token == execution_token,
            )
            .values(
                status=EvaluationStatus.COMPLETED.value,
                admission_slot=None,
                execution_token=None,
            )
        )
        db.commit()
        db.close()

    monkeypatch.setattr(
        "server.modules.evaluations.orchestrator._execute_claimed_evaluation", execute
    )

    class LeaseWait:
        def __init__(self):
            self.entered = [threading.Event(), threading.Event()]
            self.calls = 0
            self.release_first = threading.Event()

        def is_set(self):
            return False

        def wait(self, timeout=None):
            self.entered[min(self.calls, 1)].set()
            call = min(self.calls, 1)
            self.calls += 1
            if call == 0:
                self.release_first.wait(timeout)
            else:
                # This must be a real, unsignaled timed wait.  A signaled
                # second barrier would mask the refreshed lease regression.
                threading.Event().wait(timeout)
            return False

    lease_wait = LeaseWait()
    thread = threading.Thread(
        target=drain_evaluation_queue,
        args=(factory,),
        kwargs={"stop_event": lease_wait},
    )
    thread.start()
    assert lease_wait.entered[0].wait(1)
    # Refresh in the middle of the original lease interval.
    time.sleep(0.3)
    db = factory()
    try:
        assert heartbeat_evaluation_execution(db, job_id, token)
    finally:
        db.close()
    # Let the original expiry pass before releasing the first wait.  Recovery
    # must observe the refreshed row and take a distinct second wait.
    remaining = original_expiry + 0.1 - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)
    lease_wait.release_first.set()
    assert lease_wait.entered[1].wait(1)
    assert calls == []
    thread.join(3)
    assert not thread.is_alive() and calls == [job_id]


def test_clean_tokenless_submitted_is_not_recovered(tmp_path, monkeypatch) -> None:
    factory = _file_session_factory(tmp_path / "clean.db")
    session = factory()
    job = _make_job(session)
    job_id = job.evaluation_id
    session.close()
    monkeypatch.setattr(
        "server.core.config.get_settings",
        lambda: type("S", (), {"evaluation_heartbeat_stale_seconds": 0.01})(),
    )
    assert recover_interrupted_evaluation_jobs(factory) == 0
    db = factory()
    assert db.get(EvaluationJob, job_id).status == EvaluationStatus.SUBMITTED.value
    db.close()


def test_fifo_and_held_slot_prevent_second_claim() -> None:
    factory = _make_session_factory()
    db = factory()
    try:
        first, second = _make_job(db), _make_job(db)
        first.submitted_at = second.submitted_at = datetime(2020, 1, 1, tzinfo=UTC)
        db.commit()
        expected = min(first.evaluation_id, second.evaluation_id)
        token = uuid4()
        assert acquire_next_evaluation_execution(db, token) == expected
        assert acquire_next_evaluation_execution(db, uuid4()) is None
        assert db.get(EvaluationJob, expected).admission_slot == 1
    finally:
        db.close()


def test_drain_claim_exception_is_contained_and_lock_released() -> None:
    calls = 0

    class BrokenSession:
        def rollback(self):
            pass

        def close(self):
            pass

    def factory():
        nonlocal calls
        calls += 1
        return BrokenSession()

    # The helper must not leak an exception or retain its process lock.
    drain_evaluation_queue(factory)
    drain_evaluation_queue(factory)
    assert calls == 2


def test_simultaneous_drains_collapse_under_process_lock(monkeypatch) -> None:
    entered = threading.Event()
    release = threading.Event()

    def blocked(*args, **kwargs):
        entered.set()
        release.wait(1)

    monkeypatch.setattr(
        "server.modules.evaluations.orchestrator.acquire_next_evaluation_execution",
        blocked,
    )

    class Session:
        def close(self):
            pass

    thread = threading.Thread(target=drain_evaluation_queue, args=(lambda: Session(),))
    thread.start()
    entered.wait(1)
    drain_evaluation_queue(lambda: Session())
    release.set()
    thread.join(1)
