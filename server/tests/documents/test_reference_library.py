"""Tests for reference library: access rules, admin APIs, delete/rebuild.

Covers tasks 1.1-1.4, 2.1-2.4, 3.1-3.7 from
openspec/changes/reference-library-core/tasks.md
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock
from unittest.mock import patch

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents import persistence
from server.modules.documents.models import Document, DocumentChunk
from server.modules.documents.schemas import REFERENCE_SOURCE_TYPES

_TEST_PASSWORD = "password123"

# ── Helpers ─────────────────────────────────────────────────────────


def _add_doc(
    db_session,
    *,
    owner_id,
    source_type: str = "slm",
    title: str = "Test Doc",
    processing_status: str = "PROCESSED",
    file_path: str | None = None,
):
    """Create a Document row in the test database."""
    doc_id = uuid.uuid4()
    if file_path is None:
        file_path = f"uploads/{doc_id}.pdf"
    db_session.add(
        Document(
            document_id=doc_id,
            title=title,
            program="BSCS",
            source_type=source_type,
            file_path=file_path,
            uploaded_by=owner_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status=processing_status,
        )
    )
    db_session.commit()
    return doc_id


def _add_chunk(db_session, *, document_id, source_type: str = "slm"):
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
            chroma_stored=True,
        )
    )
    db_session.commit()


def _login(client, email, password=None):
    if password is None:
        password = _TEST_PASSWORD
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    return resp


# ── Task 1: Backend access rules ────────────────────────────────────


class TestReferenceSourceTypeHelpers:
    """1.1 Reference source-type helpers for syllabus and curriculum."""

    def test_reference_source_types_defined(self):
        assert "syllabus" in REFERENCE_SOURCE_TYPES
        assert "curriculum" in REFERENCE_SOURCE_TYPES
        assert "slm" not in REFERENCE_SOURCE_TYPES
        assert "rubric_sme" not in REFERENCE_SOURCE_TYPES

    def test_is_reference_helper(self, db_session):
        from server.modules.documents.access import is_reference_source_type

        assert is_reference_source_type("syllabus") is True
        assert is_reference_source_type("curriculum") is True
        assert is_reference_source_type("slm") is False
        assert is_reference_source_type("rubric_sme") is False


class TestSharedReferenceAccess:
    """1.2 Document detail/list access: references shared, SLMs owner-only."""

    def test_faculty_can_read_admin_uploaded_reference(self, client, db_session):
        """Faculty can GET a syllabus reference uploaded by admin."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        ref_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Shared Syllabus",
        )

        _login(client, faculty.email)
        resp = client.get(f"/api/v1/documents/{ref_id}")
        assert resp.status_code == 200
        assert resp.json()["source_type"] == "syllabus"

    def test_faculty_cannot_read_other_faculty_slm(self, client, db_session):
        """Faculty cannot GET another faculty's SLM (owner-only)."""
        fac1 = create_user(
            db_session,
            name="F1",
            email="f1@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        fac2 = create_user(
            db_session,
            name="F2",
            email="f2@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        slm_id = _add_doc(
            db_session, owner_id=fac1.user_id, source_type="slm", title="F1 SLM"
        )

        _login(client, fac2.email)
        resp = client.get(f"/api/v1/documents/{slm_id}")
        assert resp.status_code == 404

    def test_admin_cannot_read_faculty_slm(self, client, db_session, seeded_user):
        """Admin cannot GET a faculty's SLM."""
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        slm_id = _add_doc(
            db_session, owner_id=faculty.user_id, source_type="slm", title="Faculty SLM"
        )

        _login(client, seeded_user.email, "correct-horse-battery")
        resp = client.get(f"/api/v1/documents/{slm_id}")
        assert resp.status_code == 404

    def test_list_includes_shared_references(self, client, db_session):
        """Faculty listing documents should include shared references + own SLMs."""
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Admin Syllabus",
        )
        _add_doc(
            db_session, owner_id=faculty.user_id, source_type="slm", title="My SLM"
        )
        _add_doc(
            db_session, owner_id=admin.user_id, source_type="slm", title="Admin SLM"
        )

        _login(client, faculty.email)
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        data = resp.json()
        titles = {item["title"] for item in data["items"]}
        assert "Admin Syllabus" in titles  # shared reference
        assert "My SLM" in titles  # own SLM
        assert "Admin SLM" not in titles  # other user's SLM


class TestEvaluationSharedReferenceValidation:
    """1.3 Faculty can attach shared syllabus references to own SLM evaluations."""

    def test_faculty_uses_shared_syllabus_reference(self, db_session):
        """Faculty-owned SLM + admin-uploaded shared syllabus reference validate."""
        from server.modules.evaluations.schemas import EvaluationSubmitRequest
        from server.modules.evaluations.service import create_evaluation
        from server.tests.evaluations.conftest import _seed_active_prompts

        _seed_active_prompts(db_session)

        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        slm_id = _add_doc(db_session, owner_id=faculty.user_id, source_type="slm")
        # Admin-uploaded shared reference
        syllabus_id = _add_doc(
            db_session, owner_id=admin.user_id, source_type="syllabus"
        )

        # 'PROCESSED' + chunks + chroma_stored already set by _add_doc
        _add_chunk(db_session, document_id=slm_id, source_type="slm")
        _add_chunk(db_session, document_id=syllabus_id, source_type="syllabus")

        response = create_evaluation(
            EvaluationSubmitRequest(
                document_id=slm_id,
                syllabus_id=syllabus_id,
                partial_without_curriculum=True,
                confirmed_program="BSCS",
            ),
            submitted_by=faculty.user_id,
            db=db_session,
        )

        assert response.document_id == slm_id
        assert response.syllabus_id == syllabus_id
        assert response.curriculum_id is None
        assert response.partial_without_curriculum is True

    def test_faculty_cannot_evaluate_other_faculty_slm_even_with_shared_refs(
        self, db_session
    ):
        """Ownership check for SLM remains strict even if refs are shared."""
        from server.modules.documents.exceptions import (
            DocumentNotFoundError as DocNotFound,
        )
        from server.modules.evaluations.schemas import EvaluationSubmitRequest
        from server.modules.evaluations.service import create_evaluation

        fac1 = create_user(
            db_session,
            name="F1",
            email="f1@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        fac2 = create_user(
            db_session,
            name="F2",
            email="f2@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        slm_id = _add_doc(db_session, owner_id=fac1.user_id, source_type="slm")
        _add_chunk(db_session, document_id=slm_id, source_type="slm")

        with pytest.raises(DocNotFound):
            create_evaluation(
                EvaluationSubmitRequest(
                    document_id=slm_id,
                    partial_without_curriculum=True,
                    confirmed_program="BSCS",
                ),
                submitted_by=fac2.user_id,
                db=db_session,
            )

    def test_shared_reference_must_be_processed(self, db_session):
        """References must be PROCESSED and have embedded chunks."""
        from server.modules.evaluations.schemas import EvaluationSubmitRequest
        from server.modules.evaluations.service import create_evaluation

        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        slm_id = _add_doc(db_session, owner_id=faculty.user_id, source_type="slm")
        _add_chunk(db_session, document_id=slm_id, source_type="slm")

        pending_syllabus = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            processing_status="PENDING",
        )

        with pytest.raises(Exception) as exc_info:
            create_evaluation(
                EvaluationSubmitRequest(
                    document_id=slm_id,
                    syllabus_id=pending_syllabus,
                    partial_without_curriculum=True,
                    confirmed_program="BSCS",
                ),
                submitted_by=faculty.user_id,
                db=db_session,
            )
        assert "InvalidEvaluationTargetError" in type(exc_info.value).__name__


# ── Task 2: Reference library backend APIs ──────────────────────────


class TestAdminReferenceList:
    """2.1-2.2 Admin-only reference library list endpoint."""

    def test_admin_lists_references(self, client, db_session):
        """Admin can list syllabus and curriculum reference documents."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Syllabus A",
        )
        _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Curriculum B",
        )
        # Faculty SLM should not appear in reference list
        _add_doc(
            db_session, owner_id=faculty.user_id, source_type="slm", title="Faculty SLM"
        )

        _login(client, admin.email)
        resp = client.get("/api/v1/documents/references")
        assert resp.status_code == 200, (
            f"Expected 200 got {resp.status_code}: {resp.text[:200]}"
        )
        data = resp.json()
        titles = {item["title"] for item in data["items"]}
        assert "Syllabus A" in titles
        assert "Curriculum B" in titles
        assert "Faculty SLM" not in titles
        assert len(data["items"]) == 2
        assert data["total"] == 2

    def test_reference_list_has_health_fields(self, client, db_session):
        """Reference list items include computed health indicators."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        doc_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Health Check",
        )
        _add_chunk(db_session, document_id=doc_id, source_type="syllabus")

        _login(client, admin.email)
        resp = client.get("/api/v1/documents/references")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        # Health fields present
        assert "file_exists" in item
        assert "chunk_count" in item
        assert "chroma_available" in item
        assert "embedding_ready" in item
        assert item["chunk_count"] == 1
        assert "document_id" in item
        assert "source_type" in item
        assert "uploaded_at" in item

    def test_faculty_cannot_access_reference_list(self, client, db_session):
        """Faculty gets 403 on admin reference list."""
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        _login(client, faculty.email)
        resp = client.get("/api/v1/documents/references")
        assert resp.status_code == 403

    def test_reference_list_excludes_rubrics(self, client, db_session):
        """Rubrics do not appear in reference list; syllabus and curriculum do."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        _add_doc(
            db_session, owner_id=admin.user_id, source_type="syllabus", title="Syllabus"
        )
        _add_doc(
            db_session, owner_id=admin.user_id, source_type="rubric_sme", title="Rubric"
        )
        _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Curriculum",
        )

        _login(client, admin.email)
        resp = client.get("/api/v1/documents/references")
        assert resp.status_code == 200
        titles = {item["title"] for item in resp.json()["items"]}
        assert "Syllabus" in titles
        assert "Curriculum" in titles
        assert "Rubric" not in titles

    def test_reference_list_empty(self, client, db_session):
        """Empty reference list returns empty items."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        _login(client, admin.email)
        resp = client.get("/api/v1/documents/references")
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0}


class TestDocumentFileEndpoint:
    """2.3 Authenticated PDF file endpoint."""

    def test_faculty_can_preview_shared_reference_pdf(self, client, db_session):
        """Faculty can preview a shared reference PDF."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        pdf_path = Path("/tmp/test_ref_preview.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 test")

        try:
            ref_id = _add_doc(
                db_session,
                owner_id=admin.user_id,
                source_type="syllabus",
                title="Ref PDF",
                file_path=str(pdf_path),
            )

            _login(client, faculty.email)
            resp = client.get(f"/api/v1/documents/{ref_id}/file")
            assert resp.status_code == 200
            assert resp.headers.get("content-type") == "application/pdf"
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_faculty_cannot_preview_other_faculty_slm_pdf(self, client, db_session):
        """Faculty cannot preview another faculty's SLM PDF."""
        fac1 = create_user(
            db_session,
            name="F1",
            email="f1@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        fac2 = create_user(
            db_session,
            name="F2",
            email="f2@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        pdf_path = Path("/tmp/test_slm_preview.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 slm")

        try:
            slm_id = _add_doc(
                db_session,
                owner_id=fac1.user_id,
                source_type="slm",
                title="SLM PDF",
                file_path=str(pdf_path),
            )

            _login(client, fac2.email)
            resp = client.get(f"/api/v1/documents/{slm_id}/file")
            assert resp.status_code == 404
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_file_preview_missing_file(self, client, db_session):
        """Missing local PDF returns 404."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        ref_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Missing PDF",
            file_path="/nonexistent/path.pdf",
        )

        _login(client, admin.email)
        resp = client.get(f"/api/v1/documents/{ref_id}/file")
        assert resp.status_code == 404

    def test_file_preview_requires_auth(self, client, db_session):
        """Unauthenticated request returns 401."""
        resp = client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000/file")
        assert resp.status_code == 401


# ── Task 3: Chroma cleanup and rebuild ──────────────────────────────


class TestEmbeddingHelpers:
    """3.1 Embedding helpers for Chroma delete and check."""

    def test_delete_chroma_vectors_safe_call(self):
        """delete_chroma_vectors returns False for missing collection gracefully."""
        from server.modules.embeddings.service import delete_chroma_vectors

        # Isolate Chroma state: simulate a client with no matching collection so
        # this deterministically exercises the safe no-collection path even when
        # a collection exists in the environment.
        fake_client = mock.Mock()
        fake_client.get_collection.side_effect = RuntimeError("no such collection")
        with patch(
            "server.modules.embeddings.service.get_chroma_client",
            return_value=fake_client,
        ):
            result = delete_chroma_vectors(str(uuid.uuid4()), "syllabus")
        assert result is False

    def test_delete_chroma_vectors_strict_missing_collection(self):
        """delete_chroma_vectors_strict treats missing collection as benign False."""
        from chromadb.errors import NotFoundError
        from server.modules.embeddings.service import delete_chroma_vectors_strict

        fake_client = mock.Mock()
        fake_client.get_collection.side_effect = NotFoundError(
            "Collection [curriculum] does not exist"
        )
        with patch(
            "server.modules.embeddings.service.get_chroma_client",
            return_value=fake_client,
        ):
            result = delete_chroma_vectors_strict(str(uuid.uuid4()), "curriculum")
        assert result is False

    def test_delete_chroma_vectors_strict_propagates_unrelated_not_found_error(self):
        """delete_chroma_vectors_strict propagates unrelated errors with 'not found'."""
        from server.modules.embeddings.service import delete_chroma_vectors_strict

        fake_client = mock.Mock()
        fake_client.get_collection.side_effect = RuntimeError("host not found")
        with patch(
            "server.modules.embeddings.service.get_chroma_client",
            return_value=fake_client,
        ):
            with pytest.raises(RuntimeError, match="host not found"):
                delete_chroma_vectors_strict(str(uuid.uuid4()), "curriculum")

    def test_delete_chroma_vectors_strict_propagates_connection_error(self):
        """delete_chroma_vectors_strict propagates connection failures."""
        from server.modules.embeddings.service import delete_chroma_vectors_strict

        fake_client = mock.Mock()
        fake_client.get_collection.side_effect = ConnectionError("Chroma down")
        with patch(
            "server.modules.embeddings.service.get_chroma_client",
            return_value=fake_client,
        ):
            with pytest.raises(ConnectionError, match="Chroma down"):
                delete_chroma_vectors_strict(str(uuid.uuid4()), "curriculum")

    def test_delete_chroma_vectors_strict_verifies_zero_remaining(self):
        """delete_chroma_vectors_strict raises if vectors remain after delete."""
        from server.modules.embeddings.service import delete_chroma_vectors_strict

        fake_collection = mock.Mock()
        fake_collection.get.return_value = {"ids": ["remaining-vector-id"]}
        fake_client = mock.Mock()
        fake_client.get_collection.return_value = fake_collection

        with patch(
            "server.modules.embeddings.service.get_chroma_client",
            return_value=fake_client,
        ):
            with pytest.raises(RuntimeError, match="vectors remain"):
                delete_chroma_vectors_strict(str(uuid.uuid4()), "curriculum")

    def test_check_chroma_availability_safe_call(self):
        """check_chroma_availability returns False gracefully with no Chroma."""
        from server.modules.embeddings.service import check_chroma_availability

        result = check_chroma_availability(str(uuid.uuid4()), "syllabus")
        assert result is False


class TestCountDocumentReferences:
    """The delete-lock gate counts jobs referencing a doc via syllabus/curriculum.

    ``delete_reference_document`` delegates its 409-conflict check to the
    explicit ``count_document_references`` interface in the evaluations
    module instead of importing ``EvaluationJob`` directly.
    """

    def test_counts_syllabus_and_curriculum_references(self, db_session) -> None:
        from server.modules.evaluations.document_references import (
            count_document_references,
        )
        from server.modules.evaluations.models import EvaluationJob, EvaluationStatus

        doc_id = uuid.uuid4()
        other_id = uuid.uuid4()

        def _job(*, syllabus=None, curriculum=None):
            db_session.add(
                EvaluationJob(
                    evaluation_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    syllabus_id=syllabus,
                    curriculum_id=curriculum,
                    status=EvaluationStatus.SUBMITTED.value,
                    submitted_at=datetime.now(UTC),
                )
            )
            db_session.commit()

        _job(syllabus=doc_id)
        _job(curriculum=doc_id)
        _job(syllabus=other_id)  # references a different document

        assert count_document_references(doc_id, db_session) == 2
        assert count_document_references(other_id, db_session) == 1
        assert count_document_references(uuid.uuid4(), db_session) == 0

    def test_returns_zero_without_db(self) -> None:
        from server.modules.evaluations.document_references import (
            count_document_references,
        )

        assert count_document_references(uuid.uuid4()) == 0


class TestAdminDelete:
    """3.2-3.4 Admin delete with conflict detection and missing asset tolerance."""

    def test_admin_delete_reference(self, client, db_session):
        """Admin can delete a reference document."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        pdf_path = Path("/tmp/test_del_ref.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 delete")

        try:
            ref_id = _add_doc(
                db_session,
                owner_id=admin.user_id,
                source_type="syllabus",
                title="To Delete",
                file_path=str(pdf_path),
            )
            _add_chunk(db_session, document_id=ref_id, source_type="syllabus")

            _login(client, admin.email)
            resp = client.delete(f"/api/v1/documents/{ref_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["deleted"] is True
            assert data["document_id"] == str(ref_id)

            # Document row is gone
            assert db_session.get(Document, ref_id) is None
            # DocumentChunk rows are gone
            assert (
                db_session.query(DocumentChunk)
                .filter(DocumentChunk.document_id == ref_id)
                .count()
                == 0
            )
            # PDF file is gone
            assert not pdf_path.exists()
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_delete_reference_preserves_sql_on_unlink_error(self, client, db_session):
        """When file unlink raises OSError, returns 503 and preserves SQL/chunks."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        pdf_path = Path("/tmp/test_unlink_err.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 err")

        try:
            ref_id = _add_doc(
                db_session,
                owner_id=admin.user_id,
                source_type="syllabus",
                title="Unlink Error Doc",
                file_path=str(pdf_path),
            )
            _add_chunk(db_session, document_id=ref_id, source_type="syllabus")

            _login(client, admin.email)
            with (
                patch(
                    "server.modules.documents.syllabus.service.delete_chroma_vectors_strict",
                    return_value=True,
                ),
                patch.object(
                    Path,
                    "unlink",
                    side_effect=PermissionError("unlink permission denied"),
                ),
            ):
                resp = client.delete(f"/api/v1/documents/{ref_id}")

            assert resp.status_code == 503
            assert (
                resp.json()["detail"]
                == "Reference storage cleanup is temporarily unavailable."
            )
            # SQL document and chunks must remain preserved
            assert db_session.get(Document, ref_id) is not None
            assert (
                db_session.query(DocumentChunk)
                .filter(DocumentChunk.document_id == ref_id)
                .count()
                == 1
            )
            assert pdf_path.exists()
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_delete_reference_preserves_sql_on_file_verification_failure(
        self, client, db_session
    ):
        """When file still exists after unlink, returns 503 and preserves SQL."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        pdf_path = Path("/tmp/test_verify_fail.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 verify")

        try:
            ref_id = _add_doc(
                db_session,
                owner_id=admin.user_id,
                source_type="syllabus",
                title="Verify Fail Doc",
                file_path=str(pdf_path),
            )
            _add_chunk(db_session, document_id=ref_id, source_type="syllabus")

            _login(client, admin.email)
            # Simulate unlink doing nothing by patching unlink to no-op
            with (
                patch(
                    "server.modules.documents.syllabus.service.delete_chroma_vectors_strict",
                    return_value=True,
                ),
                patch.object(Path, "unlink", return_value=None),
            ):
                resp = client.delete(f"/api/v1/documents/{ref_id}")

            assert resp.status_code == 503
            assert (
                resp.json()["detail"]
                == "Reference storage cleanup is temporarily unavailable."
            )
            # SQL document and chunks must remain preserved
            assert db_session.get(Document, ref_id) is not None
            assert (
                db_session.query(DocumentChunk)
                .filter(DocumentChunk.document_id == ref_id)
                .count()
                == 1
            )
        finally:
            pdf_path.unlink(missing_ok=True)

    def test_delete_conflict_when_referenced_by_evaluation(self, client, db_session):
        """Delete returns 409 when evaluation jobs reference the document."""
        from server.modules.evaluations.models import EvaluationJob, EvaluationStatus

        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        syllabus_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Referenced Syllabus",
        )

        # Create an evaluation job that references the syllabus
        db_session.add(
            EvaluationJob(
                evaluation_id=uuid.uuid4(),
                document_id=uuid.uuid4(),  # unrelated slm
                syllabus_id=syllabus_id,
                status=EvaluationStatus.SUBMITTED.value,
                submitted_by=admin.user_id,
                submitted_at=datetime.now(UTC),
            )
        )
        db_session.commit()

        _login(client, admin.email)
        resp = client.delete(f"/api/v1/documents/{syllabus_id}")
        assert resp.status_code == 409
        assert "referenced" in resp.json()["detail"].lower()

    def test_delete_succeeds_for_curriculum(self, client, db_session):
        """Admin can delete an unreferenced curriculum document."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        curr_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Curriculum To Delete",
        )
        _add_chunk(db_session, document_id=curr_id, source_type="curriculum")

        _login(client, admin.email)
        with patch(
            "server.modules.documents.syllabus.service.delete_chroma_vectors_strict",
            return_value=True,
        ):
            resp = client.delete(f"/api/v1/documents/{curr_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert db_session.get(Document, curr_id) is None
        assert (
            db_session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == curr_id)
            .count()
            == 0
        )

    def test_delete_curriculum_preserves_sql_on_vector_failure(
        self, client, db_session
    ):
        """When Chroma client fails during delete, delete aborts and preserves SQL."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        curr_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Curriculum Vector Fail",
        )
        _add_chunk(db_session, document_id=curr_id, source_type="curriculum")

        mock_chroma_client = mock.MagicMock()
        mock_chroma_client.get_collection.side_effect = ConnectionError(
            "Chroma connection failed"
        )

        _login(client, admin.email)
        with patch(
            "server.modules.embeddings.service.get_chroma_client",
            return_value=mock_chroma_client,
        ):
            resp = client.delete(f"/api/v1/documents/{curr_id}")
        assert resp.status_code == 503
        assert (
            resp.json()["detail"]
            == "Reference storage cleanup is temporarily unavailable."
        )
        # Row and chunks must remain preserved
        assert db_session.get(Document, curr_id) is not None
        assert (
            db_session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == curr_id)
            .count()
            == 1
        )

    def test_delete_tolerates_missing_local_file(self, client, db_session):
        """Delete completes even when the local PDF file is missing."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        ref_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Missing File",
            file_path="/nonexistent/missing.pdf",
        )

        _login(client, admin.email)
        resp = client.delete(f"/api/v1/documents/{ref_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert db_session.get(Document, ref_id) is None

    def test_faculty_cannot_delete_reference(self, client, db_session):
        """Faculty gets 403 on reference delete."""
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        _login(client, faculty.email)
        resp = client.delete(f"/api/v1/documents/{uuid.uuid4()}")
        assert resp.status_code == 403

    def test_admin_cannot_delete_slm_through_reference_endpoint(
        self, client, db_session
    ):
        """DELETE /documents/{id} rejects SLM documents with 422."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        slm_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="slm",
            title="SLM Not Deletable",
        )

        _login(client, admin.email)
        resp = client.delete(f"/api/v1/documents/{slm_id}")
        assert resp.status_code == 422
        assert "reference document" in resp.json()["detail"].lower()

    def test_admin_cannot_delete_rubric_through_reference_endpoint(
        self, client, db_session
    ):
        """DELETE /documents/{id} rejects rubric documents with 422."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        rubric_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="rubric_sme",
            title="Rubric Not Deletable",
        )

        _login(client, admin.email)
        resp = client.delete(f"/api/v1/documents/{rubric_id}")
        assert resp.status_code == 422
        assert "reference document" in resp.json()["detail"].lower()


class TestAdminRebuild:
    """3.5-3.6 Admin rebuild endpoint."""

    def test_admin_rebuild_embeddings(self, client, db_session):
        """Admin can rebuild embeddings from existing chunks."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        ref_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Rebuild Me",
        )
        _add_chunk(db_session, document_id=ref_id, source_type="syllabus")

        with patch(
            "server.modules.documents.syllabus.service.embed_and_store_chunks"
        ) as mock_embed:
            mock_embed.return_value = 1
            _login(client, admin.email)
            resp = client.post(f"/api/v1/documents/{ref_id}/rebuild-embeddings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rebuilt"] is True
        assert data["chunk_count"] == 1

    def test_rebuild_no_chunks_fails(self, client, db_session):
        """Rebuild rejected when no chunks exist."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        ref_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="No Chunks",
        )
        # No chunks added

        _login(client, admin.email)
        resp = client.post(f"/api/v1/documents/{ref_id}/rebuild-embeddings")
        assert resp.status_code == 422
        assert "no stored chunks" in resp.json()["detail"].lower()

    def test_rebuild_unsupported_source_type_fails(self, client, db_session):
        """Rebuild rejected for non-reference source types."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        slm_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="slm",
            title="SLM Not Rebuildable",
        )
        _add_chunk(db_session, document_id=slm_id, source_type="slm")

        _login(client, admin.email)
        resp = client.post(f"/api/v1/documents/{slm_id}/rebuild-embeddings")
        assert resp.status_code == 422

    def test_faculty_cannot_rebuild(self, client, db_session):
        """Faculty gets 403 on rebuild."""
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        _login(client, faculty.email)
        resp = client.post(f"/api/v1/documents/{uuid.uuid4()}/rebuild-embeddings")
        assert resp.status_code == 403

    def test_rebuild_succeeds_for_curriculum(self, client, db_session):
        """Admin can rebuild embeddings for a curriculum document."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        curr_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Curriculum To Rebuild",
        )
        _add_chunk(db_session, document_id=curr_id, source_type="curriculum")

        with patch(
            "server.modules.documents.syllabus.service.embed_and_store_chunks"
        ) as mock_embed:
            mock_embed.return_value = 1
            _login(client, admin.email)
            resp = client.post(f"/api/v1/documents/{curr_id}/rebuild-embeddings")
        assert resp.status_code == 200
        assert resp.json()["rebuilt"] is True
        assert resp.json()["chunk_count"] == 1

    def test_rebuild_sets_chroma_stored(self, client, db_session):
        """Rebuild marks chunks chroma_stored for evaluation readiness."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        ref_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Chroma Rebuild",
        )

        # Add a chunk with chroma_stored=False (simulating initial state)
        chunk_id = uuid.uuid4()
        db_session.add(
            DocumentChunk(
                chunk_id=chunk_id,
                document_id=ref_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=1,
                text="rebuild chroma test chunk",
                token_count=4,
                is_ocr=False,
                chroma_stored=False,
            )
        )
        db_session.commit()

        with patch(
            "server.modules.documents.syllabus.service.embed_and_store_chunks"
        ) as mock_embed:
            mock_embed.return_value = 1
            _login(client, admin.email)
            resp = client.post(f"/api/v1/documents/{ref_id}/rebuild-embeddings")
        assert resp.status_code == 200

        # Verify chunk is now chroma_stored=True
        chunk = db_session.get(DocumentChunk, chunk_id)
        assert chunk is not None
        assert chunk.chroma_stored is True


class TestCurriculumAccessRules:
    """Curriculum access: shared preview/detail, generic list excluded for faculty."""

    def test_owner_and_faculty_detail_allowed_for_curriculum(self, client, db_session):
        """Authenticated faculty can view curriculum details."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        curr_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Active Curriculum",
        )

        _login(client, faculty.email)
        resp = client.get(f"/api/v1/documents/{curr_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Active Curriculum"

    def test_curriculum_excluded_from_generic_list_for_faculty(
        self, client, db_session
    ):
        """Faculty generic document list does not expose curriculum discovery."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Curriculum Ref",
        )
        _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Active Syllabus",
        )
        _add_doc(
            db_session, owner_id=faculty.user_id, source_type="slm", title="Own SLM"
        )

        _login(client, faculty.email)
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        titles = {item["title"] for item in resp.json()["items"]}
        assert "Curriculum Ref" not in titles
        assert "Own SLM" in titles

    def test_faculty_can_preview_shared_curriculum_file(self, client, db_session):
        """Authenticated faculty can stream/preview a shared curriculum PDF."""
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        pdf_path = Path("/tmp/test_curriculum_preview.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 curriculum content")

        try:
            curr_id = _add_doc(
                db_session,
                owner_id=admin.user_id,
                source_type="curriculum",
                title="Curriculum Preview",
                file_path=str(pdf_path),
            )

            _login(client, faculty.email)
            resp = client.get(f"/api/v1/documents/{curr_id}/file")
            assert resp.status_code == 200
            assert resp.content == b"%PDF-1.4 curriculum content"
        finally:
            pdf_path.unlink(missing_ok=True)


class TestSLMOwnershipStrict:
    """1.4 SLM ownership remains strict; shared references work."""

    def test_ownership_mask_on_detail(self, client, db_session):
        """SLM detail returns 404 for non-owners."""
        fac1 = create_user(
            db_session,
            name="F1",
            email="f1@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        fac2 = create_user(
            db_session,
            name="F2",
            email="f2@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        slm_id = _add_doc(
            db_session, owner_id=fac1.user_id, source_type="slm", title="Owned SLM"
        )

        for email in (fac2.email,):
            _login(client, email)
            resp = client.get(f"/api/v1/documents/{slm_id}")
            assert resp.status_code == 404

    def test_ownership_mask_on_list(self, client, db_session):
        """SLMs from other users do not appear in list."""
        fac1 = create_user(
            db_session,
            name="F1",
            email="f1@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        fac2 = create_user(
            db_session,
            name="F2",
            email="f2@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()

        _add_doc(db_session, owner_id=fac1.user_id, source_type="slm", title="F1 SLM")

        _login(client, fac2.email)
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        titles = {item["title"] for item in resp.json()["items"]}
        assert "F1 SLM" not in titles


@pytest.fixture(autouse=True)
def _cleanup_global_state():
    """Clean up shared in-memory state to avoid polluting other tests."""
    yield
    ids_to_remove = []
    for doc_id, doc in list(persistence._MEM_DOCUMENTS.items()):
        if doc.source_type in REFERENCE_SOURCE_TYPES:
            ids_to_remove.append(doc_id)
    for doc_id in ids_to_remove:
        persistence._MEM_DOCUMENTS.pop(doc_id, None)
        persistence._MEM_DOCUMENT_OWNERS.pop(doc_id, None)
        persistence._MEM_CHUNKS.pop(doc_id, None)
