"""Service-layer tests for evaluations: create_evaluation scenarios.

All new faculty evaluations are curriculum-retired partial evaluations: they
must explicitly set ``partial_without_curriculum=True``, carry no
``curriculum_id``, and confirm a valid institutional program.
"""

from __future__ import annotations

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.schemas import EvaluationSubmitRequest
from server.modules.evaluations.service import create_evaluation

from .conftest import _add_document, _seed_active_prompts


def test_create_evaluation_persists_submitted_job_for_owned_docs(db_session) -> None:
    """A curriculum-retired partial evaluation persists confirmed_program."""
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
    _seed_active_prompts(db_session)

    response = create_evaluation(
        EvaluationSubmitRequest(
            document_id=slm_id,
            syllabus_id=syllabus_id,
            partial_without_curriculum=True,
            confirmed_program="BSCS",
        ),
        submitted_by=owner.user_id,
        db=db_session,
    )

    assert response.status == EvaluationStatus.SUBMITTED
    assert response.document_id == slm_id
    assert response.syllabus_id == syllabus_id
    assert response.curriculum_id is None
    assert response.partial_without_curriculum is True
    assert response.confirmed_program == "BSCS"
    row = db_session.get(EvaluationJob, response.evaluation_id)
    assert row is not None
    assert row.status == EvaluationStatus.SUBMITTED.value
    assert row.submitted_by == owner.user_id
    assert row.confirmed_program == "BSCS"


def test_create_evaluation_without_syllabus_succeeds(db_session) -> None:
    """Can submit an evaluation with SLM only (no syllabus)."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-no-syllabus@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    response = create_evaluation(
        EvaluationSubmitRequest(
            document_id=slm_id,
            partial_without_curriculum=True,
            confirmed_program="BSCS",
        ),
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


def test_create_evaluation_requires_partial_intent(db_session) -> None:
    """Submitting without explicit partial intent raises InvalidEvaluationTargetError."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-no-partial@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                partial_without_curriculum=False,
                confirmed_program="BSCS",
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "InvalidEvaluationTargetError"
    assert "partial" in str(exc_info.value).lower()


def test_create_evaluation_requires_confirmed_program(db_session) -> None:
    """Submitting without a valid confirmed program raises InvalidEvaluationTargetError."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-no-program@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    # Missing confirmed_program entirely is rejected by the request schema.
    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                partial_without_curriculum=True,
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )
    assert exc_info.value.__class__.__name__ == "ValidationError"

    # Invalid program code.
    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                partial_without_curriculum=True,
                confirmed_program="NOT-A-PROGRAM",
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )
    assert exc_info.value.__class__.__name__ == "InvalidEvaluationTargetError"
    assert "program" in str(exc_info.value).lower()


def test_create_evaluation_rejects_curriculum_id(db_session) -> None:
    """Supplying a curriculum_id is retired and rejected."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-curriculum@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    curriculum_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="curriculum"
    )

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                curriculum_id=curriculum_id,
                partial_without_curriculum=True,
                confirmed_program="BSCS",
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "InvalidEvaluationTargetError"
    assert "curriculum" in str(exc_info.value).lower()


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
    _seed_active_prompts(db_session)

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                syllabus_id=syllabus_id,
                partial_without_curriculum=True,
                confirmed_program="BSCS",
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

    syllabus_id = _add_document(
        db_session,
        owner_id=owner.user_id,
        source_type="syllabus",
        chroma_stored=False,
    )
    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                syllabus_id=syllabus_id,
                partial_without_curriculum=True,
                confirmed_program="BSCS",
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "InvalidEvaluationTargetError"
    assert db_session.query(EvaluationJob).count() == 0


def test_create_evaluation_partial_without_curriculum_accepted(db_session) -> None:
    """Submitting without curriculum_id but with explicit partial flag succeeds."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-partial@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    _seed_active_prompts(db_session)

    response = create_evaluation(
        EvaluationSubmitRequest(
            document_id=slm_id,
            partial_without_curriculum=True,
            confirmed_program="BSCS",
        ),
        submitted_by=owner.user_id,
        db=db_session,
    )

    assert response.status == EvaluationStatus.SUBMITTED
    assert response.curriculum_id is None
    assert response.partial_without_curriculum is True
    assert response.confirmed_program == "BSCS"
    assert response.partial_reason is not None
    assert "curriculum" in response.partial_reason.lower()
    row = db_session.get(EvaluationJob, response.evaluation_id)
    assert row is not None
    assert row.partial_without_curriculum is True
    assert row.partial_reason is not None


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

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                partial_without_curriculum=True,
                confirmed_program="BSCS",
            ),
            submitted_by=other.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "DocumentNotFoundError"
    assert db_session.query(EvaluationJob).count() == 0
