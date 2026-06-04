"""Service-layer tests for evaluations: create_evaluation scenarios."""

from __future__ import annotations

from uuid import uuid4

import pytest

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.schemas import EvaluationSubmitRequest
from server.modules.evaluations.service import create_evaluation

from .conftest import _add_document, _seed_active_prompts


def test_create_evaluation_persists_submitted_job_for_owned_docs(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-submit@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )
    curriculum_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="curriculum"
    )
    _seed_active_prompts(db_session)

    response = create_evaluation(
        EvaluationSubmitRequest(
            document_id=slm_id,
            syllabus_id=syllabus_id,
            curriculum_id=curriculum_id,
        ),
        submitted_by=owner.user_id,
        db=db_session,
    )

    assert response.status == EvaluationStatus.SUBMITTED
    assert response.document_id == slm_id
    assert response.syllabus_id == syllabus_id
    assert response.curriculum_id == curriculum_id
    row = db_session.get(EvaluationJob, response.evaluation_id)
    assert row is not None
    assert row.status == EvaluationStatus.SUBMITTED.value
    assert row.submitted_by == owner.user_id


def test_create_evaluation_without_reference_documents(db_session) -> None:
    """Can submit an evaluation with only an SLM document."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-no-refs@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    response = create_evaluation(
        EvaluationSubmitRequest(document_id=slm_id),
        submitted_by=owner.user_id,
        db=db_session,
    )

    assert response.status == EvaluationStatus.SUBMITTED
    assert response.syllabus_id is None
    assert response.curriculum_id is None
    row = db_session.get(EvaluationJob, response.evaluation_id)
    assert row is not None
    assert row.syllabus_id is None
    assert row.curriculum_id is None


def test_create_evaluation_rejects_ineligible_documents(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-ineligible@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session,
        owner_id=owner.user_id,
        source_type="syllabus",
        processing_status="PENDING",
    )
    curriculum_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="curriculum"
    )
    _seed_active_prompts(db_session)

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                syllabus_id=syllabus_id,
                curriculum_id=curriculum_id,
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "InvalidEvaluationTargetError"
    assert db_session.query(EvaluationJob).count() == 0


def test_create_evaluation_rejects_documents_without_embedding_readiness(
    db_session,
) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-embedding@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    curriculum_id = _add_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        chroma_stored=False,
    )
    syllabus_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )
    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                syllabus_id=syllabus_id,
                curriculum_id=curriculum_id,
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "InvalidEvaluationTargetError"
    assert db_session.query(EvaluationJob).count() == 0


def test_create_evaluation_masks_foreign_documents_as_404(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-foreign@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email="other-foreign@example.com",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )
    curriculum_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="curriculum"
    )

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                syllabus_id=syllabus_id,
                curriculum_id=curriculum_id,
            ),
            submitted_by=other.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "DocumentNotFoundError"
    assert db_session.query(EvaluationJob).count() == 0
