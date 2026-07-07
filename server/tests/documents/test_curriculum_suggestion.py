"""Tests for curriculum suggestion endpoint and curriculum program validation.

Covers tasks 1.6 and 2.3 from
openspec/changes/program-confirmed-curriculum-selection/tasks.md:

1.6 — detected program, missing program requiring selection, multiple
      matches, no match, unhealthy curriculum, empty program validation,
      case normalization, and SLM ownership denial.

2.3 — curriculum upload without program and with program.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk
from server.modules.documents.service import (
    _MEM_CHUNKS,
    _MEM_DOCUMENTS,
    _MEM_DOCUMENT_OWNERS,
)

_TEST_PASSWORD = "password123"


# ── Helpers ─────────────────────────────────────────────────────────


def _add_doc(
    db_session,
    *,
    owner_id,
    source_type: str = "slm",
    title: str = "Test Doc",
    program: str | None = "BSCS",
    processing_status: str = "PROCESSED",
    file_path: str | None = None,
    uploaded_at: datetime | None = None,
):
    """Create a Document row in the test database."""
    doc_id = uuid.uuid4()
    if file_path is None:
        file_path = f"uploads/{doc_id}.pdf"
    if uploaded_at is None:
        uploaded_at = datetime.now(UTC)
    db_session.add(
        Document(
            document_id=doc_id,
            title=title,
            program=program,
            source_type=source_type,
            file_path=file_path,
            uploaded_by=owner_id,
            uploaded_at=uploaded_at,
            page_count=1,
            has_ocr_pages=False,
            processing_status=processing_status,
        )
    )
    db_session.commit()
    return doc_id


def _add_chunk(
    db_session, *, document_id, source_type: str = "slm", chroma_stored: bool = True
):
    """Create a DocumentChunk row."""
    db_session.add(
        DocumentChunk(
            chunk_id=uuid.uuid4(),
            document_id=document_id,
            source_type=source_type,
            agent_domain="all",
            page_number=1,
            text=f"chunk for {source_type}",
            token_count=4,
            is_ocr=False,
            chroma_stored=chroma_stored,
        )
    )
    db_session.commit()


def _login(client, email, password=None):
    if password is None:
        password = _TEST_PASSWORD
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return resp


# ── Task 1.6: Curriculum suggestion tests ───────────────────────────


class TestCurriculumSuggestion:
    """Backend curriculum suggestion endpoint tests."""

    def test_detected_program_returned(self, client, db_session):
        """Suggestion response includes the detected program from the SLM."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@detect.com",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@detect.com",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        # Faculty uploads SLM with detected program "BSCS"
        slm_id = _add_doc(
            db_session,
            owner_id=faculty.user_id,
            source_type="slm",
            title="My SLM",
            program="BSCS",
        )
        _add_chunk(db_session, document_id=slm_id, source_type="slm")

        # Admin uploads a matching curriculum
        curr_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="BSCS CHED Curriculum",
            program="BSCS",
        )
        _add_chunk(db_session, document_id=curr_id, source_type="curriculum")

        with patch(
            "server.modules.embeddings.service.check_chroma_availability"
        ) as mock_chroma:
            mock_chroma.return_value = True
            _login(client, faculty.email)
            resp = client.get(
                f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=BSCS"
            )
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["document_id"] == str(slm_id)
        assert data["detected_program"] == "BSCS"
        assert data["selected_program"] == "BSCS"
        assert len(data["curriculum_suggestions"]) == 1
        assert data["curriculum_suggestions"][0]["title"] == "BSCS CHED Curriculum"
        assert data["preferred_suggestion"] is not None
        assert data["preferred_suggestion"]["document_id"] == str(curr_id)

    def test_missing_program_requires_selection(self, client, db_session):
        """When SLM has no detected program, endpoint still works with explicit program."""
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@noprogram.com",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        slm_id = _add_doc(
            db_session,
            owner_id=faculty.user_id,
            source_type="slm",
            title="No Program SLM",
            program=None,
        )
        _add_chunk(db_session, document_id=slm_id, source_type="slm")

        _login(client, faculty.email)
        resp = client.get(
            f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=BSCS"
        )
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["detected_program"] is None
        assert data["selected_program"] == "BSCS"

    def test_multiple_matches_returns_newest_preferred(self, client, db_session):
        """When multiple curricula match, the newest is preferred."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@multi.com",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@multi.com",
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

        # Older curriculum
        old_curr = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="BSCS Curriculum v1",
            program="BSCS",
            uploaded_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        _add_chunk(db_session, document_id=old_curr, source_type="curriculum")

        # Newer curriculum
        new_curr = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="BSCS Curriculum v2",
            program="BSCS",
            uploaded_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        _add_chunk(db_session, document_id=new_curr, source_type="curriculum")

        with patch(
            "server.modules.embeddings.service.check_chroma_availability"
        ) as mock_chroma:
            mock_chroma.return_value = True
            _login(client, faculty.email)
            resp = client.get(
                f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=BSCS"
            )
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert len(data["curriculum_suggestions"]) == 2
        # Preferred is newest
        assert data["preferred_suggestion"]["document_id"] == str(new_curr)
        # Both are in the list
        doc_ids = [c["document_id"] for c in data["curriculum_suggestions"]]
        assert str(old_curr) in doc_ids
        assert str(new_curr) in doc_ids

    def test_no_match_returns_empty_lists(self, client, db_session):
        """When no curriculum exists for the program, empty lists are returned."""
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@nomatch.com",
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
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["curriculum_suggestions"] == []
        assert data["unavailable_curricula"] == []
        assert data["preferred_suggestion"] is None

    def test_unhealthy_curriculum_appears_in_unavailable(self, client, db_session):
        """A curriculum that exists but is not embedding-ready shows as unavailable."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@unhealthy.com",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@unhealthy.com",
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

        # Curriculum with PENDING status (not embedding-ready)
        pending_curr = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="BSCS Curriculum Pending",
            program="BSCS",
            processing_status="PENDING",
        )
        # No chunks added

        _login(client, faculty.email)
        resp = client.get(
            f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=BSCS"
        )
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["curriculum_suggestions"] == []
        assert data["preferred_suggestion"] is None
        assert len(data["unavailable_curricula"]) == 1
        assert (
            data["unavailable_curricula"][0]["document_id"] == str(pending_curr)
        )
        assert data["unavailable_curricula"][0]["embedding_ready"] is False

    def test_empty_program_returns_422(self, client, db_session):
        """Empty program returns 422 validation error, not all curricula."""
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@emptyprog.com",
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
            f"/api/v1/documents/{slm_id}/curriculum-suggestion?program="
        )
        assert resp.status_code == 422, f"Got {resp.status_code}: {resp.text}"

    def test_empty_program_whitespace_returns_422(self, client, db_session):
        """Whitespace-only program returns 422 validation error."""
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@whitespace.com",
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
            f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=%20%20%20"
        )
        # FastAPI's min_length catches empty string, but whitespace-only
        # would pass min_length=1. Our service catches it.
        # Whitespace-only: "   " is URL-encoded as %20%20%20
        # FastAPI will receive "   " which passes min_length=1
        # Our service will raise ValueError after strip()
        assert resp.status_code == 422, f"Got {resp.status_code}: {resp.text}"
        assert "empty" in resp.json()["detail"].lower()

    def test_case_normalization(self, client, db_session):
        """Program matching is case-insensitive (uppercased on comparison)."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@case.com",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@case.com",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        slm_id = _add_doc(
            db_session,
            owner_id=faculty.user_id,
            source_type="slm",
            title="My SLM",
            program="bscs",  # lowercase
        )
        _add_chunk(db_session, document_id=slm_id, source_type="slm")

        # Curriculum stored as uppercase "BSCS"
        curr_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="BSCS Curriculum",
            program="BSCS",
        )
        _add_chunk(db_session, document_id=curr_id, source_type="curriculum")

        with patch(
            "server.modules.embeddings.service.check_chroma_availability"
        ) as mock_chroma:
            mock_chroma.return_value = True

            # Query with lowercase
            _login(client, faculty.email)
            resp = client.get(
                f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=bscs"
            )
            assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert len(data["curriculum_suggestions"]) == 1

            # Query with mixed case
            resp2 = client.get(
                f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=Bscs"
            )
            assert resp2.status_code == 200, f"Got {resp2.status_code}: {resp2.text}"
            data2 = resp2.json()
            assert len(data2["curriculum_suggestions"]) == 1

    def test_slm_ownership_denial(self, client, db_session):
        """Faculty cannot get curriculum suggestions for another faculty's SLM."""
        fac1 = create_user(
            db_session,
            name="Faculty1",
            email="faculty1@own.com",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        fac2 = create_user(
            db_session,
            name="Faculty2",
            email="faculty2@own.com",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        slm_id = _add_doc(
            db_session,
            owner_id=fac1.user_id,
            source_type="slm",
            title="F1 SLM",
            program="BSCS",
        )
        _add_chunk(db_session, document_id=slm_id, source_type="slm")

        _login(client, fac2.email)
        resp = client.get(
            f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=BSCS"
        )
        assert resp.status_code == 404, f"Got {resp.status_code}: {resp.text}"

    def test_endpoint_requires_auth(self, client):
        """Unauthenticated request returns 401."""
        resp = client.get(
            f"/api/v1/documents/{uuid.uuid4()}/curriculum-suggestion?program=BSCS"
        )
        assert resp.status_code == 401

    def test_non_slm_document_id_rejected(self, client, db_session):
        """Curriculum suggestion for a non-SLM document returns 422."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@non-slm.com",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        # Upload a syllabus document
        syllabus_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="A Syllabus",
            program="BSCS",
        )
        _add_chunk(db_session, document_id=syllabus_id, source_type="syllabus")

        # Upload a curriculum document
        curr_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="A Curriculum",
            program="BSCS",
        )
        _add_chunk(db_session, document_id=curr_id, source_type="curriculum")

        _login(client, admin.email)

        # Try suggesting curriculum for a syllabus document
        resp = client.get(
            f"/api/v1/documents/{syllabus_id}/curriculum-suggestion?program=BSCS"
        )
        assert resp.status_code == 422, f"Got {resp.status_code}: {resp.text}"
        assert "slm" in resp.json()["detail"].lower()

        # Try suggesting curriculum for a curriculum document
        resp2 = client.get(
            f"/api/v1/documents/{curr_id}/curriculum-suggestion?program=BSCS"
        )
        assert resp2.status_code == 422, f"Got {resp2.status_code}: {resp2.text}"
        assert "slm" in resp2.json()["detail"].lower()

    def test_mixed_ready_and_unavailable(self, client, db_session):
        """Both ready and unavailable curricula are returned in their respective lists."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@mixed.com",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@mixed.com",
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

        # Ready curriculum
        ready_curr = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="BSCS Ready",
            program="BSCS",
        )
        _add_chunk(db_session, document_id=ready_curr, source_type="curriculum")

        # Unavailable curriculum (no chunks)
        bad_curr = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="BSCS Unavailable",
            program="BSCS",
            processing_status="PENDING",
        )

        with patch(
            "server.modules.embeddings.service.check_chroma_availability"
        ) as mock_chroma:
            mock_chroma.return_value = True

            _login(client, faculty.email)
            resp = client.get(
                f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=BSCS"
            )
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert len(data["curriculum_suggestions"]) == 1
        assert data["curriculum_suggestions"][0]["document_id"] == str(ready_curr)
        assert len(data["unavailable_curricula"]) == 1
        assert data["unavailable_curricula"][0]["document_id"] == str(bad_curr)
        assert data["preferred_suggestion"]["document_id"] == str(ready_curr)


# ── Task 2.3: Curriculum upload validation tests ────────────────────


class TestCurriculumUploadValidation:
    """Admin curriculum upload requires program."""

    def test_curriculum_upload_without_program_fails(self, client, db_session):
        """Uploading a curriculum without program returns 422."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@noprogramupload.com",
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
                "title": "Curriculum Without Program",
                # program omitted
            },
        )
        assert resp.status_code == 422, f"Got {resp.status_code}: {resp.text}"
        assert "program" in resp.json()["detail"].lower()

    def test_curriculum_upload_with_program_succeeds(self, client, db_session):
        """Uploading a curriculum with program succeeds."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@withprogram.com",
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
        assert resp.status_code == 201, f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["source_type"] == "curriculum"

    def test_syllabus_upload_without_program_still_succeeds(self, client, db_session):
        """Syllabus uploads do not require program (only curriculum does)."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@syllabusnoprogram.com",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        _login(client, admin.email)
        resp = client.post(
            "/api/v1/documents/upload",
            files={
                "file": (
                    "syllabus.pdf",
                    b"%PDF-1.4\nminimal",
                    "application/pdf",
                )
            },
            data={
                "source_type": "syllabus",
                "title": "Syllabus Without Program",
                # program omitted
            },
        )
        assert resp.status_code == 201, f"Got {resp.status_code}: {resp.text}"

    def test_curriculum_upload_with_empty_program_fails(self, client, db_session):
        """Uploading a curriculum with empty program string returns 422."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@emptyprogramupload.com",
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
                "title": "Curriculum Empty Program",
                "program": "",
            },
        )
        assert resp.status_code == 422, f"Got {resp.status_code}: {resp.text}"
        assert "program" in resp.json()["detail"].lower()


@pytest.fixture(autouse=True)
def _cleanup_test_state():
    """Clean up in-memory state after each test."""
    yield
    _MEM_CHUNKS.clear()
    _MEM_DOCUMENTS.clear()
    _MEM_DOCUMENT_OWNERS.clear()
