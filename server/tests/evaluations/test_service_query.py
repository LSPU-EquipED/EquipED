"""Service-layer tests for evaluations: get, list, status scenarios."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.schemas import EvaluationListItem
from server.modules.evaluations.service import (
    get_evaluation,
    get_evaluation_status,
    list_evaluations,
)

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
    """Evaluation list items should include document_title for human-readable display."""
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

    response = list_evaluations(1, 20, owner.user_id, UserRole.FACULTY.value, db_session)
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

    response = list_evaluations(1, 20, owner.user_id, UserRole.FACULTY.value, db_session)
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

    db_session.add_all([
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
    ])
    db_session.commit()

    # Without filter: both evaluations
    all_resp = list_evaluations(1, 20, owner.user_id, UserRole.FACULTY.value, db_session)
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
        partial_reason="No curriculum reference was available; Coordinator review was skipped.",
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
