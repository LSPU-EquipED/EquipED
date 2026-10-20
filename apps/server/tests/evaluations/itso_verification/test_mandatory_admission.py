"""Adapter-3 admission always requires configured public-reference tools."""

import uuid

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.admission import create_evaluation
from server.modules.evaluations.itso.exceptions import ITSOError
from server.modules.evaluations.models import EvaluationJob
from server.modules.evaluations.schemas import EvaluationSubmitRequest
from server.tests.rubrics.helpers import seed_all_rubrics


@pytest.mark.parametrize("verification", [None, False])
def test_itso_v3_admission_checks_readiness_and_freezes_true(
    db_session, monkeypatch, verification
):
    readiness_checks = []

    def ready(*, needs_search=True):
        readiness_checks.append(needs_search)

    monkeypatch.setattr(
        "server.modules.evaluations.itso.reference_tools.ensure_public_reference_tools_ready",
        ready,
    )
    faculty = create_user(
        db_session,
        name="ITSO Verification Faculty",
        email=f"itso-verification-{uuid.uuid4()}@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    document = Document(
        document_id=uuid.uuid4(),
        title="ITSO module",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/itso-module.pdf",
        uploaded_by=faculty.user_id,
        processing_status="PROCESSED",
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=document.document_id,
            source_type="slm",
            agent_domain="itso",
            page_number=1,
            text="References\n[1] Ada Author (2024). Public reference study.",
            chunk_index=0,
        )
    )
    seed_all_rubrics(db_session)
    db_session.flush()
    request_values = {
        "document_id": document.document_id,
        "target_agent": "itso",
        "confirmed_program": "BSCS",
    }
    if verification is not None:
        request_values["external_verification"] = verification

    submitted = create_evaluation(
        EvaluationSubmitRequest(**request_values),
        submitted_by=faculty.user_id,
        submitted_by_role=UserRole.FACULTY.value,
        db=db_session,
    )

    job = db_session.get(EvaluationJob, submitted.evaluation_id)
    assert readiness_checks == [True]
    assert job.adapter_request == {"itso_reference_verification": True}


@pytest.mark.parametrize("verification", [None, False])
def test_itso_v3_admission_fails_closed_when_tools_are_unready(
    db_session, monkeypatch, verification
):
    from server.modules.evaluations.itso.reference_tools import (
        ReferenceToolsUnavailable,
    )
    from server.modules.evaluations.itso.verification.contracts import Code

    def unavailable(*, needs_search=True):
        assert needs_search
        raise ReferenceToolsUnavailable(Code.DISABLED)

    monkeypatch.setattr(
        "server.modules.evaluations.itso.reference_tools.ensure_public_reference_tools_ready",
        unavailable,
    )
    faculty = create_user(
        db_session,
        name="ITSO Unready Faculty",
        email=f"itso-unready-{uuid.uuid4()}@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    document = Document(
        document_id=uuid.uuid4(),
        title="ITSO module",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/itso-unready.pdf",
        uploaded_by=faculty.user_id,
        processing_status="PROCESSED",
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=document.document_id,
            source_type="slm",
            agent_domain="itso",
            page_number=1,
            text="References\n[1] Ada Author (2024). Public reference study.",
            chunk_index=0,
        )
    )
    seed_all_rubrics(db_session)
    request_values = {
        "document_id": document.document_id,
        "target_agent": "itso",
        "confirmed_program": "BSCS",
    }
    if verification is not None:
        request_values["external_verification"] = verification

    with pytest.raises(ITSOError) as error:
        create_evaluation(
            EvaluationSubmitRequest(**request_values),
            submitted_by=faculty.user_id,
            submitted_by_role=UserRole.FACULTY.value,
            db=db_session,
        )

    assert (error.value.code, error.value.status) == (
        Code.DISABLED.value,
        503,
    )
    assert db_session.query(EvaluationJob).count() == 0


@pytest.mark.parametrize("adapter_version", [None, 1, 2])
def test_admission_rejects_missing_or_retired_itso_activation(
    db_session, monkeypatch, adapter_version
):
    faculty = create_user(
        db_session,
        name="Retired ITSO Faculty",
        email=f"retired-itso-{uuid.uuid4()}@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    document = Document(
        document_id=uuid.uuid4(),
        title="ITSO module",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/retired-itso.pdf",
        uploaded_by=faculty.user_id,
        processing_status="PROCESSED",
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=document.document_id,
            source_type="slm",
            agent_domain="itso",
            page_number=1,
            text="Learning resources\nAda Author (2024). Public study.",
            chunk_index=0,
        )
    )
    db_session.flush()
    monkeypatch.setattr(
        "server.modules.rubrics.get_active_rubric_adapter_version",
        lambda *args, **kwargs: adapter_version,
    )

    def unexpected_tools(**kwargs):
        pytest.fail("retired activation reached public tools")

    monkeypatch.setattr(
        "server.modules.evaluations.itso.reference_tools.ensure_public_reference_tools_ready",
        unexpected_tools,
    )
    with pytest.raises(ITSOError, match="itso_harness_upgrade_required") as error:
        create_evaluation(
            EvaluationSubmitRequest(
                document_id=document.document_id,
                target_agent="itso",
                confirmed_program="BSCS",
            ),
            submitted_by=faculty.user_id,
            submitted_by_role=UserRole.FACULTY.value,
            db=db_session,
        )
    assert error.value.status == 503
    assert db_session.query(EvaluationJob).count() == 0
