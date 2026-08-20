"""Service-layer tests for evaluations: get, list, status scenarios."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.schemas import EvaluationListItem
from server.modules.evaluations.service import (
    get_evaluation,
    get_evaluation_status,
    get_latest_evaluations,
    list_evaluations,
)
from sqlalchemy import event

from .conftest import _add_document


def test_get_and_status_mask_foreign_jobs_as_404(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-job@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email="other-job@example.com",
        password="password456",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        syllabus_id=uuid4(),
        curriculum_id=uuid4(),
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(job)
    db_session.commit()

    with pytest.raises(Exception) as get_exc:
        get_evaluation(job.evaluation_id, other.user_id, other.role.value, db_session)
    with pytest.raises(Exception) as status_exc:
        get_evaluation_status(
            job.evaluation_id, other.user_id, other.role.value, db_session
        )

    assert get_exc.value.__class__.__name__ == "EvaluationNotFoundError"
    assert status_exc.value.__class__.__name__ == "EvaluationNotFoundError"


@pytest.mark.parametrize("role", [UserRole.FACULTY, UserRole.ADMIN])
def test_list_evaluations_is_scoped_per_user_for_all_roles(db_session, role) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email=f"owner-list-{role.value}@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email=f"other-list-{role.value}@example.com",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    db_session.add_all(
        [
            EvaluationJob(
                evaluation_id=uuid4(),
                document_id=uuid4(),
                syllabus_id=uuid4(),
                curriculum_id=uuid4(),
                status=EvaluationStatus.SUBMITTED.value,
                error_message=None,
                submitted_by=owner.user_id,
                submitted_at=datetime.now(UTC),
                completed_at=None,
            ),
            EvaluationJob(
                evaluation_id=uuid4(),
                document_id=uuid4(),
                syllabus_id=uuid4(),
                curriculum_id=uuid4(),
                status=EvaluationStatus.SUBMITTED.value,
                error_message=None,
                submitted_by=other.user_id,
                submitted_at=datetime.now(UTC),
                completed_at=None,
            ),
        ]
    )
    db_session.commit()

    response = list_evaluations(1, 20, owner.user_id, role.value, db_session)
    assert response.total == 1
    assert all(item.document_id for item in response.items)
    assert all(item.syllabus_id for item in response.items)
    assert all(item.curriculum_id for item in response.items)


def test_list_evaluations_includes_document_title(db_session) -> None:
    """Evaluation list items include document_title for human-readable display."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-title@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="slm", with_chunks=True
    )

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_id,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(job)
    db_session.commit()

    response = list_evaluations(
        1, 20, owner.user_id, UserRole.FACULTY.value, db_session
    )
    assert response.total == 1
    item = response.items[0]
    assert isinstance(item, EvaluationListItem)
    assert item.document_title == "slm doc"
    assert item.document_id == doc_id


def test_list_evaluations_document_title_none_for_missing_document(db_session) -> None:
    """document_title should be None when the referenced document does not exist."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-missing-doc@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),  # non-existent document
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(job)
    db_session.commit()

    response = list_evaluations(
        1, 20, owner.user_id, UserRole.FACULTY.value, db_session
    )
    assert response.total == 1
    assert response.items[0].document_title is None


def test_list_evaluations_filters_by_document_id(db_session) -> None:
    """Filtering by document_id should return only evaluations for that document."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-filter-doc@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc_a = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    doc_b = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    db_session.add_all(
        [
            EvaluationJob(
                evaluation_id=uuid4(),
                document_id=doc_a,
                syllabus_id=None,
                curriculum_id=None,
                status=EvaluationStatus.SUBMITTED.value,
                error_message=None,
                submitted_by=owner.user_id,
                submitted_at=datetime.now(UTC),
                completed_at=None,
            ),
            EvaluationJob(
                evaluation_id=uuid4(),
                document_id=doc_b,
                syllabus_id=None,
                curriculum_id=None,
                status=EvaluationStatus.SUBMITTED.value,
                error_message=None,
                submitted_by=owner.user_id,
                submitted_at=datetime.now(UTC),
                completed_at=None,
            ),
        ]
    )
    db_session.commit()

    # Without filter: both evaluations
    all_resp = list_evaluations(
        1, 20, owner.user_id, UserRole.FACULTY.value, db_session
    )
    assert all_resp.total == 2

    # With filter for doc_a: only one
    filtered_resp = list_evaluations(
        1, 20, owner.user_id, UserRole.FACULTY.value, db_session, document_id=doc_a
    )
    assert filtered_resp.total == 1
    assert filtered_resp.items[0].document_id == doc_a

    # With filter for non-existent doc: zero
    empty_resp = list_evaluations(
        1, 20, owner.user_id, UserRole.FACULTY.value, db_session, document_id=uuid4()
    )
    assert empty_resp.total == 0
    assert empty_resp.items == []


def test_list_evaluations_filter_by_document_id_respects_ownership(db_session) -> None:
    """Filtering by document_id must not leak another user's evaluations."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-filter-own@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email="other-filter-own@example.com",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    # Other user has an evaluation for the same document
    db_session.add(
        EvaluationJob(
            evaluation_id=uuid4(),
            document_id=doc,
            syllabus_id=None,
            curriculum_id=None,
            status=EvaluationStatus.SUBMITTED.value,
            error_message=None,
            submitted_by=other.user_id,
            submitted_at=datetime.now(UTC),
            completed_at=None,
        )
    )
    db_session.commit()

    # Owner has no evaluations for this document
    resp = list_evaluations(
        1, 20, owner.user_id, UserRole.FACULTY.value, db_session, document_id=doc
    )
    assert resp.total == 0
    assert resp.items == []

    # Other user sees their own evaluation
    other_resp = list_evaluations(
        1, 20, other.user_id, UserRole.FACULTY.value, db_session, document_id=doc
    )
    assert other_resp.total == 1
    assert other_resp.items[0].document_id == doc


@pytest.mark.parametrize("role", [UserRole.FACULTY, UserRole.ADMIN])
def test_get_is_scoped_per_user_for_all_roles(db_session, role) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email=f"owner-get-{role.value}@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email=f"other-get-{role.value}@example.com",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        syllabus_id=uuid4(),
        curriculum_id=uuid4(),
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
    )
    db_session.add(job)
    db_session.commit()

    with pytest.raises(Exception) as exc_info:
        get_evaluation(job.evaluation_id, other.user_id, role.value, db_session)
    assert exc_info.value.__class__.__name__ == "EvaluationNotFoundError"


def test_get_evaluation_status_includes_partial_fields(db_session) -> None:
    """get_evaluation_status returns partial_without_curriculum and partial_reason
    for a deliberate no-curriculum partial evaluation."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-status-partial@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
        partial_without_curriculum=True,
        partial_reason=(
            "No curriculum reference was available; Coordinator review was skipped."
        ),
    )
    db_session.add(job)
    db_session.commit()

    response = get_evaluation_status(
        job.evaluation_id, owner.user_id, UserRole.FACULTY.value, db_session
    )

    assert response.partial_without_curriculum is True
    assert response.partial_reason is not None
    assert "curriculum" in response.partial_reason.lower()


def test_get_evaluation_status_includes_partial_fields_when_false(db_session) -> None:
    """get_evaluation_status returns partial_without_curriculum=False and
    partial_reason=None for a regular (non-partial) evaluation."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-status-full@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        syllabus_id=uuid4(),
        curriculum_id=uuid4(),
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
        partial_without_curriculum=False,
        partial_reason=None,
    )
    db_session.add(job)
    db_session.commit()

    response = get_evaluation_status(
        job.evaluation_id, owner.user_id, UserRole.FACULTY.value, db_session
    )

    assert response.partial_without_curriculum is False
    assert response.partial_reason is None


def test_get_latest_evaluations_returns_latest_per_document(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner Latest",
        email="owner-latest@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc_1 = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    doc_2 = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    t0 = datetime.now(UTC) - timedelta(hours=2)
    t1 = datetime.now(UTC) - timedelta(hours=1)
    t2 = datetime.now(UTC)

    # doc 1: two evaluations (older and newer)
    job_1_old = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_1,
        status=EvaluationStatus.FAILED.value,
        submitted_by=owner.user_id,
        submitted_at=t0,
        completed_at=t0 + timedelta(minutes=5),
        error_message="Old error",
    )
    job_1_new = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_1,
        status=EvaluationStatus.COMPLETED.value,
        submitted_by=owner.user_id,
        submitted_at=t2,
        completed_at=t2 + timedelta(minutes=5),
        error_message=None,
    )
    # doc 2: single evaluation
    job_2 = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_2,
        status=EvaluationStatus.EVALUATING.value,
        submitted_by=owner.user_id,
        submitted_at=t1,
        completed_at=None,
        error_message=None,
    )
    db_session.add_all([job_1_old, job_1_new, job_2])
    db_session.commit()
    current_user_id = owner.user_id

    statement_count = 0

    def count_statement(*_args) -> None:
        nonlocal statement_count
        statement_count += 1

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", count_statement)
    try:
        response = get_latest_evaluations(
            [doc_1, doc_2],
            current_user_id,
            db=db_session,
        )
    finally:
        event.remove(bind, "before_cursor_execute", count_statement)

    assert statement_count == 1
    assert len(response.items) == 2
    item_by_doc = {item.document_id: item for item in response.items}
    assert item_by_doc[doc_1].evaluation_id == job_1_new.evaluation_id
    assert item_by_doc[doc_1].status == EvaluationStatus.COMPLETED
    assert item_by_doc[doc_1].submitted_at == job_1_new.submitted_at
    assert item_by_doc[doc_1].completed_at == job_1_new.completed_at
    assert item_by_doc[doc_1].error_message is None

    assert item_by_doc[doc_2].evaluation_id == job_2.evaluation_id
    assert item_by_doc[doc_2].status == EvaluationStatus.EVALUATING


def test_get_latest_evaluations_deterministic_tie_break(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner Tiebreak",
        email="owner-tiebreak@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    same_time = datetime.now(UTC)

    id_low = UUID("00000000-0000-0000-0000-000000000001")
    id_high = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    job_low = EvaluationJob(
        evaluation_id=id_low,
        document_id=doc,
        status=EvaluationStatus.FAILED.value,
        submitted_by=owner.user_id,
        submitted_at=same_time,
    )
    job_high = EvaluationJob(
        evaluation_id=id_high,
        document_id=doc,
        status=EvaluationStatus.COMPLETED.value,
        submitted_by=owner.user_id,
        submitted_at=same_time,
    )
    db_session.add_all([job_low, job_high])
    db_session.commit()

    response = get_latest_evaluations([doc], owner.user_id, db=db_session)
    assert len(response.items) == 1
    # Deterministic tie-break by evaluation_id DESC selects id_high
    assert response.items[0].evaluation_id == id_high
    assert response.items[0].status == EvaluationStatus.COMPLETED


def test_get_latest_evaluations_ownership_exclusion(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner Excl",
        email="owner-excl@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other Excl",
        email="other-excl@example.com",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc_own = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    doc_other = _add_document(db_session, owner_id=other.user_id, source_type="slm")

    job_own = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_own,
        status=EvaluationStatus.COMPLETED.value,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
    )
    job_other = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_other,
        status=EvaluationStatus.COMPLETED.value,
        submitted_by=other.user_id,
        submitted_at=datetime.now(UTC),
    )
    db_session.add_all([job_own, job_other])
    db_session.commit()

    # Querying as owner for both documents returns only owner's job
    resp_owner = get_latest_evaluations(
        [doc_own, doc_other], owner.user_id, db=db_session
    )
    assert len(resp_owner.items) == 1
    assert resp_owner.items[0].document_id == doc_own
    assert resp_owner.items[0].evaluation_id == job_own.evaluation_id

    # Querying as other returns only other's job
    resp_other = get_latest_evaluations(
        [doc_own, doc_other], other.user_id, db=db_session
    )
    assert len(resp_other.items) == 1
    assert resp_other.items[0].document_id == doc_other
    assert resp_other.items[0].evaluation_id == job_other.evaluation_id


def test_get_latest_evaluations_unknown_ids_and_empty(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner Unknown",
        email="owner-unknown@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    # Empty list
    empty_resp = get_latest_evaluations([], owner.user_id, db=db_session)
    assert empty_resp.items == []

    # Non-existent document ID
    unknown_resp = get_latest_evaluations([uuid4()], owner.user_id, db=db_session)
    assert unknown_resp.items == []


def test_get_latest_evaluations_preserves_status_semantics(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner Semantics",
        email="owner-semantics@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc_partial = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    doc_failed = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    doc_active = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    t = datetime.now(UTC)
    job_partial = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_partial,
        status=EvaluationStatus.COMPLETED.value,
        submitted_by=owner.user_id,
        submitted_at=t,
        completed_at=t + timedelta(seconds=10),
        partial_without_curriculum=True,
        partial_reason="No curriculum",
    )
    job_failed = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_failed,
        status=EvaluationStatus.FAILED.value,
        submitted_by=owner.user_id,
        submitted_at=t,
        completed_at=t + timedelta(seconds=2),
        error_message="Agent execution timeout",
    )
    job_active = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=doc_active,
        status=EvaluationStatus.PREPROCESSING.value,
        submitted_by=owner.user_id,
        submitted_at=t,
        completed_at=None,
    )
    db_session.add_all([job_partial, job_failed, job_active])
    db_session.commit()

    resp = get_latest_evaluations(
        [doc_partial, doc_failed, doc_active], owner.user_id, db=db_session
    )
    assert len(resp.items) == 3
    lookup = {item.document_id: item for item in resp.items}

    assert lookup[doc_partial].status == EvaluationStatus.COMPLETED
    assert lookup[doc_partial].completed_at is not None

    assert lookup[doc_failed].status == EvaluationStatus.FAILED
    assert lookup[doc_failed].error_message == "Agent execution timeout"

    assert lookup[doc_active].status == EvaluationStatus.PREPROCESSING
    assert lookup[doc_active].completed_at is None
