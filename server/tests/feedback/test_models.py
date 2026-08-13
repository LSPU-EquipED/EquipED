"""Persistence tests for the extended PreferenceLog model."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.modules.auth.models import User, UserRole
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.feedback.models import PreferenceLog


def test_preference_log_stores_agent_and_criterion_attribution(db_session):
    user = User(
        user_id=uuid4(),
        name="Admin",
        email="admin@example.com",
        password_hash="x",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.flush()

    # Document.uploaded_by is a required (non-nullable) FK to users.user_id,
    # so the user above must be created and flushed first.
    document_id = uuid4()
    db_session.add(
        Document(
            document_id=document_id,
            title="doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=user.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.flush()

    job = EvaluationJob(evaluation_id=uuid4(), document_id=document_id)
    db_session.add(job)
    db_session.flush()

    log = PreferenceLog(
        evaluation_id=job.evaluation_id,
        user_id=user.user_id,
        agent_name="itso",
        criterion_id="itso-03",
        action="EDIT",
        edited_json={"score": 2, "justification": "Missing citation format check."},
    )
    db_session.add(log)
    db_session.commit()

    fetched = db_session.get(PreferenceLog, log.log_id)
    assert fetched.agent_name == "itso"
    assert fetched.criterion_id == "itso-03"
    assert fetched.edited_json == {
        "score": 2,
        "justification": "Missing citation format check.",
    }
