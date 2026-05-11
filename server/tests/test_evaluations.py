"""Evaluations module tests for lifecycle, scoping, and dispatch behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import run_evaluation_job
from server.modules.evaluations.service import (
    create_evaluation,
    get_evaluation,
    get_evaluation_status,
    list_evaluations,
    transition_evaluation_status,
)
from server.modules.evaluations.schemas import EvaluationSubmitRequest


class FakeSession:
    def __init__(self) -> None:
        self.jobs: dict[object, EvaluationJob] = {}
        self.added: list[EvaluationJob] = []
        self.committed = 0

    def add(self, row: EvaluationJob) -> None:
        self.jobs[row.evaluation_id] = row
        self.added.append(row)

    def commit(self) -> None:
        self.committed += 1

    def close(self) -> None:
        pass

    def get(self, model, key):
        return self.jobs.get(key)

    def query(self, model):
        return FakeQuery(list(self.jobs.values()))


class FakeQuery:
    def __init__(self, rows: list[EvaluationJob]) -> None:
        self.rows = rows

    def filter(self, predicate):
        if hasattr(predicate, "left") and hasattr(predicate, "right"):
            field_name = predicate.left.key
            value = predicate.right.value
            return FakeQuery([row for row in self.rows if getattr(row, field_name) == value])
        return self

    def count(self) -> int:
        return len(self.rows)

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.rows)


def test_create_evaluation_defaults_to_submitted() -> None:
    db = FakeSession()
    request = EvaluationSubmitRequest(document_id=uuid4())
    user_id = uuid4()

    response = create_evaluation(request, submitted_by=user_id, db=db)

    assert response.status == EvaluationStatus.SUBMITTED
    assert response.document_id == request.document_id
    assert response.submitted_by == user_id
    assert db.committed == 1
    assert len(db.added) == 1


def test_transition_rejects_invalid_state_change() -> None:
    db = FakeSession()
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        status=EvaluationStatus.SUBMITTED,
        error_message=None,
        submitted_by=uuid4(),
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db.add(job)

    try:
        transition_evaluation_status(job.evaluation_id, EvaluationStatus.EVALUATING, db)
    except Exception as exc:
        assert exc.__class__.__name__ == "InvalidStatusTransitionError"
    else:
        raise AssertionError("expected InvalidStatusTransitionError")


def test_transition_marks_terminal_completion_time() -> None:
    db = FakeSession()
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        status=EvaluationStatus.SYNTHESIZING,
        error_message=None,
        submitted_by=uuid4(),
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db.add(job)

    result = transition_evaluation_status(job.evaluation_id, EvaluationStatus.COMPLETED, db)

    assert result.status == EvaluationStatus.COMPLETED
    assert result.completed_at is not None


def test_get_evaluation_masks_non_owner_as_not_found() -> None:
    db = FakeSession()
    owner = uuid4()
    other = uuid4()
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        status=EvaluationStatus.SUBMITTED,
        error_message=None,
        submitted_by=owner,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db.add(job)

    try:
        get_evaluation(job.evaluation_id, other, UserRole.FACULTY.value, db)
    except Exception as exc:
        assert exc.__class__.__name__ == "EvaluationNotFoundError"
    else:
        raise AssertionError("expected EvaluationNotFoundError")


def test_list_evaluations_filters_by_owner() -> None:
    db = FakeSession()
    owner = uuid4()
    other = uuid4()
    db.add(
        EvaluationJob(
            evaluation_id=uuid4(),
            document_id=uuid4(),
            status=EvaluationStatus.SUBMITTED,
            error_message=None,
            submitted_by=owner,
            submitted_at=datetime.now(UTC),
            completed_at=None,
        )
    )
    db.add(
        EvaluationJob(
            evaluation_id=uuid4(),
            document_id=uuid4(),
            status=EvaluationStatus.SUBMITTED,
            error_message=None,
            submitted_by=other,
            submitted_at=datetime.now(UTC),
            completed_at=None,
        )
    )

    response = list_evaluations(1, 20, owner, UserRole.FACULTY.value, db)

    assert response.total == 1
    assert len(response.items) == 1


def test_get_status_returns_status_only() -> None:
    db = FakeSession()
    owner = uuid4()
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        status=EvaluationStatus.EMBEDDING,
        error_message=None,
        submitted_by=owner,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db.add(job)

    response = get_evaluation_status(job.evaluation_id, owner, UserRole.FACULTY.value, db)

    assert response.status == EvaluationStatus.EMBEDDING
    assert response.evaluation_id == job.evaluation_id


def test_orchestrator_marks_completed_with_fake_session_factory() -> None:
    db = FakeSession()
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        status=EvaluationStatus.SUBMITTED,
        error_message=None,
        submitted_by=uuid4(),
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db.add(job)

    run_evaluation_job(job.evaluation_id, job.document_id, lambda: db)

    assert db.jobs[job.evaluation_id].status == EvaluationStatus.COMPLETED
    assert db.jobs[job.evaluation_id].completed_at is not None


def test_evaluation_submit_endpoint_uses_logged_in_user(client: TestClient, db_session, monkeypatch) -> None:
    faculty = create_user(
        db_session,
        name="Faculty User",
        email="faculty-eval@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password123"},
    )
    assert login.status_code == 200

    from server.modules.evaluations import router as evaluations_router_module

    monkeypatch.setattr(
        evaluations_router_module,
        "get_session_factory",
        lambda: (lambda: db_session),
    )

    response = client.post(
        "/api/v1/evaluations/",
        json={"document_id": str(uuid4())},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "SUBMITTED"


def test_router_masks_non_owner_access_as_404(client: TestClient, db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-eval@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email="other-eval@example.com",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        status=EvaluationStatus.SUBMITTED,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(job)
    db_session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": other.email, "password": "password456"},
    )

    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}")

    assert response.status_code == 404
