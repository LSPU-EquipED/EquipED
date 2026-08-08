"""Tests for retired curriculum upload and deprecated suggestion endpoint."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk

_TEST_PASSWORD = "Password123!"


def _login(client, email: str) -> None:
    client.cookies.clear()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": _TEST_PASSWORD},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"


def _add_doc(
    db_session,
    *,
    owner_id,
    source_type,
    title,
    program=None,
    processing_status="PROCESSED",
    uploaded_at=None,
):
    doc = Document(
        document_id=uuid.uuid4(),
        title=title,
        program=program,
        source_type=source_type,
        file_path=f"uploads/{uuid.uuid4()}.pdf",
        uploaded_by=owner_id,
        processing_status=processing_status,
        uploaded_at=uploaded_at or datetime.now(UTC),
    )
    db_session.add(doc)
    db_session.commit()
    return doc.document_id


def _add_chunk(db_session, *, document_id, source_type):
    chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=document_id,
        source_type=source_type,
        agent_domain="all",
        page_number=1,
        text="Sample text content for chunking test.",
        token_count=10,
        chroma_stored=True,
    )
    db_session.add(chunk)
    db_session.commit()


class TestCurriculumSuggestion:
    """Backend curriculum suggestion returns empty after retirement."""

    def test_curriculum_suggestion_returns_empty_response(self, client, db_session):
        """Deprecated suggestion returns empty for any requested program."""
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@retired.com",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        slm_id = _add_doc(
            db_session,
            owner_id=faculty.user_id,
            source_type="slm",
            title="My SLM",
            program="BSCS",
        )
        _add_chunk(db_session, document_id=slm_id, source_type="slm")

        _login(client, faculty.email)
        resp = client.get(
            f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=BSCS"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == str(slm_id)
        assert data["selected_program"] == "BSCS"
        assert data["curriculum_suggestions"] == []
        assert data["unavailable_curricula"] == []


class TestCurriculumUploadValidation:
    """Admin and faculty curriculum uploads are strictly rejected."""

    def test_curriculum_upload_rejected(self, client, db_session):
        """Uploading a curriculum document returns 422 rejected."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@retired_upload.com",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        _login(client, admin.email)
        resp = client.post(
            "/api/v1/documents/upload",
            files={
                "file": (
                    "curriculum.pdf",
                    b"%PDF-1.4\nminimal",
                    "application/pdf",
                )
            },
            data={
                "source_type": "curriculum",
                "title": "Curriculum With Program",
                "program": "BSCS",
            },
        )
        assert resp.status_code == 422
        assert "retired" in resp.json()["detail"].lower()
