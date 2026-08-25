"""Service-layer tests for evaluations: create_evaluation scenarios.

Evaluations support optional curriculum references:
- Full evaluations: valid curriculum_id + partial_without_curriculum=False.
- Partial evaluations: no curriculum_id + partial_without_curriculum=True.
- Program confirmation on write accepts only BSCS or BSInfoTech (rejects BSIT).
"""

from __future__ import annotations

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document
from server.modules.evaluations.exceptions import InvalidEvaluationTargetError
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.schemas import EvaluationSubmitRequest
from server.modules.evaluations.service import create_evaluation

from .conftest import _add_document, _seed_active_prompts


def test_create_evaluation_partial_persists_submitted_job_for_owned_docs(
    db_session,
) -> None:
    """A partial evaluation persists confirmed_program and partial fields."""
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
    assert response.partial_reason is not None
    assert "curriculum" in response.partial_reason.lower()
    row = db_session.get(EvaluationJob, response.evaluation_id)
    assert row is not None
    assert row.status == EvaluationStatus.SUBMITTED.value
    assert row.submitted_by == owner.user_id
    assert row.confirmed_program == "BSCS"
    assert row.partial_without_curriculum is True


def test_create_evaluation_full_persists_submitted_job_with_curriculum(
    db_session,
    monkeypatch,
) -> None:
    """A full evaluation with ready admin curriculum persists curriculum_id and full intent."""  # noqa: E501
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: True,
    )
    admin = create_user(
        db_session,
        name="Admin",
        email="admin-full@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-full@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    syllabus_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )
    curriculum_id = _add_document(
        db_session, owner_id=admin.user_id, source_type="curriculum"
    )
    _seed_active_prompts(db_session)

    response = create_evaluation(
        EvaluationSubmitRequest(
            document_id=slm_id,
            syllabus_id=syllabus_id,
            curriculum_id=curriculum_id,
            partial_without_curriculum=False,
            confirmed_program="BSCS",
        ),
        submitted_by=owner.user_id,
        db=db_session,
    )

    assert response.status == EvaluationStatus.SUBMITTED
    assert response.document_id == slm_id
    assert response.syllabus_id == syllabus_id
    assert response.curriculum_id == curriculum_id
    assert response.partial_without_curriculum is False
    assert response.partial_reason is None
    assert response.confirmed_program == "BSCS"
    row = db_session.get(EvaluationJob, response.evaluation_id)
    assert row is not None
    assert row.status == EvaluationStatus.SUBMITTED.value
    assert row.submitted_by == owner.user_id
    assert row.confirmed_program == "BSCS"
    assert row.curriculum_id == curriculum_id
    assert row.partial_without_curriculum is False
    assert row.partial_reason is None


@pytest.mark.parametrize("submitted_program", ["BSCS", "BSInfoTech"])
def test_create_evaluation_accepts_canonical_programs(
    db_session, submitted_program: str
) -> None:
    owner = create_user(
        db_session,
        name="Program Owner",
        email=f"{submitted_program.lower()}-program@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    response = create_evaluation(
        EvaluationSubmitRequest(
            document_id=slm_id,
            partial_without_curriculum=True,
            confirmed_program=submitted_program,
        ),
        submitted_by=owner.user_id,
        db=db_session,
    )

    assert response.confirmed_program == submitted_program
    row = db_session.get(EvaluationJob, response.evaluation_id)
    assert row is not None
    assert row.confirmed_program == submitted_program


@pytest.mark.parametrize(
    "submitted_program", ["BSIT", "bsit", "bsinfotech", "BSEd", "BSN"]
)  # noqa: E501
def test_create_evaluation_rejects_bsit_and_unsupported_programs_on_write(
    db_session, submitted_program: str
) -> None:
    owner = create_user(
        db_session,
        name="Unsupported Program Owner",
        email=f"unsupported-{submitted_program.lower()}@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    with pytest.raises(InvalidEvaluationTargetError, match="Only BSCS and BSInfoTech"):
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                partial_without_curriculum=True,
                confirmed_program=submitted_program,
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )


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


def test_create_evaluation_rejects_missing_curriculum_when_partial_false(
    db_session,
) -> None:
    """Submitting with partial_without_curriculum=False and no curriculum_id is rejected."""  # noqa: E501
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-no-curr-full@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    with pytest.raises(InvalidEvaluationTargetError, match="curriculum_id is required"):
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                curriculum_id=None,
                partial_without_curriculum=False,
                confirmed_program="BSCS",
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )


def test_create_evaluation_rejects_conflicting_curriculum_and_partial_true(
    db_session,
) -> None:
    """Submitting both curriculum_id and partial_without_curriculum=True is rejected."""  # noqa: E501
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-conflict@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    admin = create_user(
        db_session,
        name="Admin",
        email="admin-conflict@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    curriculum_id = _add_document(
        db_session, owner_id=admin.user_id, source_type="curriculum"
    )

    with pytest.raises(
        InvalidEvaluationTargetError, match="Cannot specify curriculum_id"
    ):
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


def test_create_evaluation_requires_confirmed_program(db_session) -> None:
    """Submitting without a valid confirmed program raises an invalid-target error."""
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
    with pytest.raises(InvalidEvaluationTargetError, match="Only BSCS and BSInfoTech"):
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                partial_without_curriculum=True,
                confirmed_program="NOT-A-PROGRAM",
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )


def test_create_evaluation_rejects_unready_curriculum(db_session, monkeypatch) -> None:
    """Unready curriculum (e.g. no chroma vectors or unbaked status) is rejected."""
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: False,
    )
    admin = create_user(
        db_session,
        name="Admin",
        email="admin-unready@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-unready@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    curriculum_id = _add_document(
        db_session, owner_id=admin.user_id, source_type="curriculum"
    )

    with pytest.raises(
        InvalidEvaluationTargetError,
        match="^Curriculum is not ready for evaluation\\.$",
    ):
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                curriculum_id=curriculum_id,
                partial_without_curriculum=False,
                confirmed_program="BSCS",
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )
    assert db_session.query(EvaluationJob).count() == 0


def test_create_evaluation_rejects_non_admin_curriculum(
    db_session, monkeypatch
) -> None:
    """Curriculum uploaded by a non-admin is rejected."""
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: True,
    )
    faculty_uploader = create_user(
        db_session,
        name="Faculty Uploader",
        email="faculty-curr-uploader@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-non-admin-curr@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    curriculum_id = _add_document(
        db_session, owner_id=faculty_uploader.user_id, source_type="curriculum"
    )

    with pytest.raises(
        InvalidEvaluationTargetError,
        match="^Curriculum is not ready for evaluation\\.$",
    ):
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                curriculum_id=curriculum_id,
                partial_without_curriculum=False,
                confirmed_program="BSCS",
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )
    assert db_session.query(EvaluationJob).count() == 0


def test_create_evaluation_rejects_program_mismatched_curriculum(
    db_session, monkeypatch
) -> None:
    """Curriculum whose program does not match confirmed_program is rejected."""
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: True,
    )
    admin = create_user(
        db_session,
        name="Admin",
        email="admin-mismatch@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-mismatch@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    curriculum_id = _add_document(
        db_session, owner_id=admin.user_id, source_type="curriculum"
    )
    # Set curriculum program to BSInfoTech
    curr_doc = db_session.get(Document, curriculum_id)
    curr_doc.program = "BSInfoTech"
    db_session.commit()

    with pytest.raises(
        InvalidEvaluationTargetError,
        match="^Curriculum is not ready for evaluation\\.$",
    ):
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                curriculum_id=curriculum_id,
                partial_without_curriculum=False,
                confirmed_program="BSCS",
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )
    assert db_session.query(EvaluationJob).count() == 0


@pytest.mark.parametrize(
    ("setup_kind", "chroma_ready"),
    [
        ("non_existent", True),
        ("wrong_source_type", True),
        ("missing_uploader_user", True),
        ("non_admin_uploader", True),
        ("program_mismatch", True),
        ("pending_status", True),
        ("failed_status", True),
        ("no_chunks", True),
        ("no_chroma_vectors", False),
    ],
)
def test_create_evaluation_unready_curriculum_parameterized(
    db_session, monkeypatch, caplog, setup_kind: str, chroma_ready: bool
) -> None:
    """Parameterized: unready curriculum states produce generic error and no job."""
    from uuid import uuid4

    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: chroma_ready,
    )

    admin = create_user(
        db_session,
        name="Admin Param",
        email=f"admin-{uuid4()}@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    faculty = create_user(
        db_session,
        name="Faculty Param",
        email=f"faculty-{uuid4()}@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=faculty.user_id, source_type="slm")

    if setup_kind == "non_existent":
        curriculum_id = uuid4()
    elif setup_kind == "wrong_source_type":
        curriculum_id = _add_document(
            db_session, owner_id=admin.user_id, source_type="syllabus"
        )
    elif setup_kind == "missing_uploader_user":
        curriculum_id = _add_document(
            db_session, owner_id=uuid4(), source_type="curriculum"
        )
    elif setup_kind == "non_admin_uploader":
        curriculum_id = _add_document(
            db_session, owner_id=faculty.user_id, source_type="curriculum"
        )
    elif setup_kind == "program_mismatch":
        curriculum_id = _add_document(
            db_session, owner_id=admin.user_id, source_type="curriculum"
        )
        curr_doc = db_session.get(Document, curriculum_id)
        curr_doc.program = "BSInfoTech"
        db_session.commit()
    elif setup_kind == "pending_status":
        curriculum_id = _add_document(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            processing_status="PENDING",
        )
    elif setup_kind == "failed_status":
        curriculum_id = _add_document(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            processing_status="FAILED",
        )
    elif setup_kind == "no_chunks":
        curriculum_id = _add_document(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            with_chunks=False,
        )
    elif setup_kind == "no_chroma_vectors":
        curriculum_id = _add_document(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            chroma_stored=False,
        )
    else:
        pytest.fail(f"Unknown setup_kind: {setup_kind}")

    with pytest.raises(
        InvalidEvaluationTargetError,
        match="^Curriculum is not ready for evaluation\\.$",
    ) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                curriculum_id=curriculum_id,
                partial_without_curriculum=False,
                confirmed_program="BSCS",
            ),
            submitted_by=faculty.user_id,
            db=db_session,
        )

    assert str(exc_info.value) == "Curriculum is not ready for evaluation."
    assert db_session.query(EvaluationJob).count() == 0


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


def test_create_evaluation_masks_owned_non_slm_as_404(db_session) -> None:
    """An owned document with non-slm source_type as primary target raises 404."""
    owner = create_user(
        db_session,
        name="Owner",
        email="owner-nonslm@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    syllabus_id = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=syllabus_id,
                partial_without_curriculum=True,
                confirmed_program="BSCS",
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "DocumentNotFoundError"
    assert db_session.query(EvaluationJob).count() == 0


def test_create_evaluation_masks_shared_non_slm_as_404(db_session) -> None:
    """A shared accessible non-slm document (e.g. admin curriculum) as primary target raises 404."""  # noqa: E501
    admin = create_user(
        db_session,
        name="Admin",
        email="admin-shared-nonslm@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    faculty = create_user(
        db_session,
        name="Faculty",
        email="faculty-shared-nonslm@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    curriculum_id = _add_document(
        db_session, owner_id=admin.user_id, source_type="curriculum"
    )

    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=curriculum_id,
                partial_without_curriculum=True,
                confirmed_program="BSCS",
            ),
            submitted_by=faculty.user_id,
            db=db_session,
        )

    assert exc_info.value.__class__.__name__ == "DocumentNotFoundError"
    assert db_session.query(EvaluationJob).count() == 0


@pytest.mark.parametrize(
    "invalid_program",
    ["INVALID_PROGRAM", "BSIT", "bsit", "BSEd"],
)
def test_create_evaluation_primary_document_masking_precedes_program_validation(
    db_session, invalid_program: str
) -> None:
    """Primary document masking (missing, foreign, non-SLM) occurs before program validation."""  # noqa: E501
    owner = create_user(
        db_session,
        name="Owner",
        email=f"owner-order-{invalid_program.lower()}@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    other = create_user(
        db_session,
        name="Other",
        email=f"other-order-{invalid_program.lower()}@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    owned_syllabus = _add_document(
        db_session, owner_id=owner.user_id, source_type="syllabus"
    )
    foreign_slm = _add_document(db_session, owner_id=other.user_id, source_type="slm")

    # 1. Owned non-SLM + invalid program -> 404 (not program validation error)
    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=owned_syllabus,
                partial_without_curriculum=True,
                confirmed_program=invalid_program,
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )
    assert exc_info.value.__class__.__name__ == "DocumentNotFoundError"

    # 2. Foreign SLM + invalid program -> 404 (not program validation error)
    with pytest.raises(Exception) as exc_info:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=foreign_slm,
                partial_without_curriculum=True,
                confirmed_program=invalid_program,
            ),
            submitted_by=owner.user_id,
            db=db_session,
        )
    assert exc_info.value.__class__.__name__ == "DocumentNotFoundError"

    assert db_session.query(EvaluationJob).count() == 0
