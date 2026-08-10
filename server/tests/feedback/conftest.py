"""Shared fixtures for feedback module tests."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.tests.admin.conftest import (  # noqa: F401 — re-exported fixtures
    admin_user,
    auth_cookies_admin,
    auth_cookies_faculty,
    faculty_user,
)


@pytest.fixture()
def evaluation_job(db_session, admin_user):  # noqa: F811 — pytest fixture shadow
    # Document.uploaded_by is a required (non-nullable) FK to users.user_id,
    # so this fixture depends on admin_user rather than passing None.
    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=admin_user.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.flush()
    job = EvaluationJob(evaluation_id=uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.commit()
    return job
