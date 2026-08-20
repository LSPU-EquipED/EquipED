"""Shared fixtures for feedback module tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.tests.admin.conftest import (  # noqa: F401 — re-exported fixtures
    admin_user,
    auth_cookies_admin,
    auth_cookies_faculty,
    faculty_user,
)


def _make_evaluation_job(db_session, *, owner_id):
    # Document.uploaded_by is a required (non-nullable) FK to users.user_id.
    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=owner_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.flush()
    # submitted_by is the ownership field create_criterion_feedback checks
    # for non-admin callers (see server/modules/feedback/service.py).
    job = EvaluationJob(
        evaluation_id=uuid4(), document_id=document_id, submitted_by=owner_id
    )
    db_session.add(job)
    db_session.flush()

    itso_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name="itso",
        subtotal=3.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="ITSO summary",
        success=True,
    )
    db_session.add(itso_result)
    db_session.flush()

    db_session.add(
        CriterionScore(
            agent_result_id=itso_result.agent_result_id,
            evaluation_id=job.evaluation_id,
            document_id=document_id,
            criterion_id="itso-03",
            criterion_title="References / Bibliography",
            score=3,
            justification="Adequate references provided.",
        )
    )

    sme_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=document_id,
        agent_name="sme",
        subtotal=4.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="SME summary",
        success=True,
    )
    db_session.add(sme_result)
    db_session.flush()

    db_session.add(
        CriterionScore(
            agent_result_id=sme_result.agent_result_id,
            evaluation_id=job.evaluation_id,
            document_id=document_id,
            criterion_id="A-01",
            criterion_title="Objective Alignment",
            score=4,
            justification="Strong alignment with syllabus objectives.",
        )
    )

    db_session.commit()
    return job


@pytest.fixture()
def evaluation_job(db_session, admin_user):  # noqa: F811 — pytest fixture shadow
    """An evaluation submitted by (owned by) the admin_user fixture."""
    return _make_evaluation_job(db_session, owner_id=admin_user.user_id)


@pytest.fixture()
def faculty_evaluation_job(db_session, faculty_user):  # noqa: F811
    """An evaluation submitted by (owned by) the faculty_user fixture."""
    return _make_evaluation_job(db_session, owner_id=faculty_user.user_id)
