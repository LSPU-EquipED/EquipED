"""Tests for curriculum reference lifecycle, extraction, readiness, and suggestions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.curriculum.extraction import filter_curriculum_pages
from server.modules.documents.curriculum.service import (
    check_curriculum_readiness,
)
from server.modules.documents.exceptions import ExtractionFailedError
from server.modules.documents.ingestion.pipeline import ExtractedPage
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
    file_path=None,
):
    doc = Document(
        document_id=uuid.uuid4(),
        title=title,
        program=program,
        source_type=source_type,
        file_path=file_path or f"uploads/{uuid.uuid4()}.pdf",
        uploaded_by=owner_id,
        processing_status=processing_status,
        uploaded_at=uploaded_at or datetime.now(UTC),
    )
    db_session.add(doc)
    db_session.commit()
    return doc.document_id


def _add_chunk(
    db_session, *, document_id, source_type="curriculum", chroma_stored=True
):
    chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=document_id,
        source_type=source_type,
        agent_domain="all",
        page_number=1,
        text="Sample text content for chunking test.",
        token_count=10,
        chroma_stored=chroma_stored,
    )
    db_session.add(chunk)
    db_session.commit()
    return chunk.chunk_id


class TestCurriculumUploadValidation:
    """Admin-only curriculum upload with canonical BSCS/BSInfoTech validation."""

    def test_admin_can_upload_canonical_bscs(self, client, db_session):
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()
        _login(client, admin.email)

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("curriculum.pdf", b"%PDF-1.4\ncontent", "application/pdf")},
            data={
                "source_type": "curriculum",
                "title": "BSCS Curriculum Map",
                "program": "BSCS",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_type"] == "curriculum"
        assert data["processing_status"] in ("PROCESSING", "PROCESSED")

    def test_admin_can_upload_canonical_bsinfotech(self, client, db_session):
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()
        _login(client, admin.email)

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("curriculum.pdf", b"%PDF-1.4\ncontent", "application/pdf")},
            data={
                "source_type": "curriculum",
                "title": "BSInfoTech Curriculum Map",
                "program": "BSInfoTech",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_type"] == "curriculum"

    def test_admin_upload_rejects_bsit_write(self, client, db_session):
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()
        _login(client, admin.email)

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("curriculum.pdf", b"%PDF-1.4\ncontent", "application/pdf")},
            data={
                "source_type": "curriculum",
                "title": "Legacy BSIT Map",
                "program": "BSIT",
            },
        )
        assert resp.status_code == 422
        assert "bsit" in resp.json()["detail"].lower()

    def test_admin_upload_rejects_missing_program(self, client, db_session):
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()
        _login(client, admin.email)

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("curriculum.pdf", b"%PDF-1.4\ncontent", "application/pdf")},
            data={
                "source_type": "curriculum",
                "title": "No Program Map",
            },
        )
        assert resp.status_code == 422
        assert "program" in resp.json()["detail"].lower()

    def test_admin_upload_rejects_unsupported_program(self, client, db_session):
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()
        _login(client, admin.email)

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("curriculum.pdf", b"%PDF-1.4\ncontent", "application/pdf")},
            data={
                "source_type": "curriculum",
                "title": "BSN Map",
                "program": "BSN",
            },
        )
        assert resp.status_code == 422

    def test_faculty_upload_of_curriculum_is_forbidden(self, client, db_session):
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()
        _login(client, faculty.email)

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("curriculum.pdf", b"%PDF-1.4\ncontent", "application/pdf")},
            data={
                "source_type": "curriculum",
                "title": "Faculty Curriculum",
                "program": "BSCS",
            },
        )
        assert resp.status_code == 403

    def test_rubric_upload_remains_rejected(self, client, db_session):
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()
        _login(client, admin.email)

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("rubric.pdf", b"%PDF-1.4\ncontent", "application/pdf")},
            data={
                "source_type": "rubric_sme",
                "title": "SME Rubric",
            },
        )
        assert resp.status_code == 422


class TestCurriculumMapFiltering:
    """Deterministic section-aware text filter tests."""

    def test_bscs_filtered_from_multi_program_pages(self):
        pages = [
            ExtractedPage(
                page_number=1,
                text=(
                    "Preamble\n"
                    "Curriculum Map for the Bachelor of Science in Computer Science\n"
                    "CS Core Outcomes\n"
                    "CS Page 1 content"
                ),
                is_ocr=False,
            ),
            ExtractedPage(
                page_number=2,
                text=(
                    "CS Page 2 content\n"
                    "Curriculum Map for the Bachelor of Science in "
                    "Information Technology\n"
                    "IT Page 2 content"
                ),
                is_ocr=False,
            ),
            ExtractedPage(
                page_number=3,
                text=(
                    "IT Page 3 content\nSection 11 Sample Means of Curriculum Delivery"
                ),
                is_ocr=False,
            ),
        ]
        filtered = filter_curriculum_pages(pages, "BSCS")
        assert len(filtered) == 2
        assert "Computer Science" in filtered[0].text
        assert "Preamble" not in filtered[0].text
        assert "CS Page 2 content" in filtered[1].text
        assert "Information Technology" not in filtered[1].text

    def test_bsinfotech_filtered_from_multi_program_pages(self):
        pages = [
            ExtractedPage(
                page_number=1,
                text=(
                    "Curriculum Map for the Bachelor of Science in Computer Science\n"
                    "CS content"
                ),
                is_ocr=False,
            ),
            ExtractedPage(
                page_number=2,
                text=(
                    "Curriculum Map for the Bachelor of Science in "
                    "Information Technology\n"
                    "IT content line 1"
                ),
                is_ocr=False,
            ),
            ExtractedPage(
                page_number=3,
                text=(
                    "IT content line 2\n"
                    "Section 11. Sample Means of Curriculum Delivery\n"
                    "Post-map section"
                ),
                is_ocr=False,
            ),
        ]
        filtered = filter_curriculum_pages(pages, "BSInfoTech")
        assert len(filtered) == 2
        assert filtered[0].page_number == 2
        assert "Information Technology" in filtered[0].text
        assert filtered[1].page_number == 3
        assert "IT content line 2" in filtered[1].text
        assert "Post-map section" not in filtered[1].text

    def test_same_page_boundary_trimming(self):
        pages = [
            ExtractedPage(
                page_number=1,
                text=(
                    "Intro header\n"
                    "Curriculum Map for the Bachelor of Science in "
                    "Computer Science\n"
                    "CS Map Table Here\n"
                    "Curriculum Map for the Bachelor of Science in "
                    "Information Technology\n"
                    "IT Map Table Here"
                ),
                is_ocr=False,
            )
        ]
        filtered = filter_curriculum_pages(pages, "BSCS")
        assert len(filtered) == 1
        assert "Intro header" not in filtered[0].text
        assert "CS Map Table Here" in filtered[0].text
        assert "IT Map Table Here" not in filtered[0].text

    def test_absent_section_fails_closed(self):
        pages = [
            ExtractedPage(
                page_number=1,
                text=(
                    "Curriculum Map for the Bachelor of Science in "
                    "Information Systems\nIS content"
                ),
                is_ocr=False,
            )
        ]
        with pytest.raises(ExtractionFailedError, match="not found"):
            filter_curriculum_pages(pages, "BSCS")

    def test_unrecognized_multi_program_indicators_fail_closed(self):
        pages = [
            ExtractedPage(
                page_number=1,
                text=(
                    "This document discusses the Bachelor of Science in "
                    "Information Technology and BSIS roadmap without "
                    "clear map headers."
                ),
                is_ocr=False,
            )
        ]
        with pytest.raises(
            ExtractionFailedError, match="Multi-program curriculum indicators"
        ):
            filter_curriculum_pages(pages, "BSCS")

    def test_single_program_clean_text_retains_all_pages(self):
        pages = [
            ExtractedPage(
                page_number=1, text="Single program CS document page 1", is_ocr=False
            ),
            ExtractedPage(
                page_number=2, text="Single program CS document page 2", is_ocr=False
            ),
        ]
        filtered = filter_curriculum_pages(pages, "BSCS")
        assert len(filtered) == 2
        assert filtered[0].text == "Single program CS document page 1"
        assert filtered[1].text == "Single program CS document page 2"

    def test_recognized_target_header_with_unrecognized_neighbor_fails_closed(self):
        pages = [
            ExtractedPage(
                page_number=1,
                text=(
                    "Curriculum Map for the Bachelor of Science in Computer Science\n"
                    "CS Content Table\n"
                    "Some un-headed neighbor section: Bachelor of Science in "
                    "Information Technology without a valid curriculum map header\n"
                    "IT table"
                ),
                is_ocr=False,
            )
        ]
        with pytest.raises(
            ExtractionFailedError,
            match="Multi-program curriculum indicators detected in retained section",
        ):
            filter_curriculum_pages(pages, "BSCS")

    def test_curriculum_fails_closed_on_empty_or_whitespace_pages(self):
        # Empty page
        pages_empty = [
            ExtractedPage(
                page_number=1,
                text=(
                    "Curriculum Map for the Bachelor of Science in "
                    "Computer Science\nCS content"
                ),
                is_ocr=False,
            ),
            ExtractedPage(
                page_number=2,
                text="",
                is_ocr=False,
            ),
        ]
        with pytest.raises(ExtractionFailedError, match="empty or unextractable pages"):
            filter_curriculum_pages(pages_empty, "BSCS")

        # Whitespace-only page
        pages_whitespace = [
            ExtractedPage(
                page_number=1,
                text=(
                    "Curriculum Map for the Bachelor of Science in "
                    "Computer Science\nCS content"
                ),
                is_ocr=False,
            ),
            ExtractedPage(
                page_number=2,
                text="   \n\t  \r\n",
                is_ocr=False,
            ),
            ExtractedPage(
                page_number=3,
                text="CS content continuation",
                is_ocr=False,
            ),
        ]
        with pytest.raises(ExtractionFailedError, match="empty or unextractable pages"):
            filter_curriculum_pages(pages_whitespace, "BSCS")

    def test_body_mention_does_not_truncate_curriculum(self):
        pages = [
            ExtractedPage(
                page_number=1,
                text=(
                    "Curriculum Map for the Bachelor of Science in Computer Science\n"
                    "CS Line 1\n"
                    "According to Section 11 of the CHED memorandum, "
                    "programs must align.\n"
                    "CS Line 2\n"
                    "The sample means of curriculum delivery are "
                    "documented in the guide.\n"
                    "Final CS Content Line"
                ),
                is_ocr=False,
            )
        ]
        filtered = filter_curriculum_pages(pages, "BSCS")
        assert len(filtered) == 1
        assert "CS Line 1" in filtered[0].text
        assert "Section 11" in filtered[0].text
        assert "CS Line 2" in filtered[0].text
        assert "sample means of curriculum delivery" in filtered[0].text
        assert "Final CS Content Line" in filtered[0].text

    @pytest.mark.parametrize(
        "heading_marker",
        [
            "Section 11",
            "SECTION 11.",
            "Section 11:",
            "Section 11 - Sample Means of Curriculum Delivery",
            "Section 11: Sample Means of Curriculum Delivery",
            "Section 11. Sample Means of Curriculum Delivery.",
            "Section 11 Sample Means of Curriculum Delivery",
            "Sample Means of Curriculum Delivery",
            "SAMPLE MEANS OF CURRICULUM DELIVERY",
            "Sample Means of Curriculum Delivery:",
            "Sample Means of Curriculum Delivery.",
        ],
    )
    def test_true_heading_stops_curriculum_extraction(self, heading_marker):
        pages = [
            ExtractedPage(
                page_number=1,
                text=(
                    "Curriculum Map for the Bachelor of Science in Computer Science\n"
                    "CS Core Course Table Line 1\n"
                    "CS Core Course Table Line 2\n"
                    f"{heading_marker}\n"
                    "Post-Map Section Content That Must Be Truncated"
                ),
                is_ocr=False,
            )
        ]
        filtered = filter_curriculum_pages(pages, "BSCS")
        assert len(filtered) == 1
        assert "CS Core Course Table Line 1" in filtered[0].text
        assert "CS Core Course Table Line 2" in filtered[0].text
        assert heading_marker not in filtered[0].text
        assert "Post-Map Section Content That Must Be Truncated" not in filtered[0].text

    def test_curriculum_ingestion_fails_closed_on_mixed_empty_page(self, monkeypatch):
        from server.modules.documents.ingestion.pipeline import ingest_document

        fake_pages = [
            ExtractedPage(
                page_number=1,
                text=(
                    "Curriculum Map for the Bachelor of Science in "
                    "Computer Science\nCS Table"
                ),
                is_ocr=False,
            ),
            ExtractedPage(
                page_number=2,
                text="   \n",
                is_ocr=False,
            ),
        ]
        monkeypatch.setattr(
            "server.modules.documents.ingestion.pipeline._extract_pages",
            lambda _: fake_pages,
        )

        with pytest.raises(ExtractionFailedError, match="empty or unextractable pages"):
            ingest_document(
                file_path="fake_path.pdf",
                source_type="curriculum",
                document_id=str(uuid.uuid4()),
                program="BSCS",
            )


class TestCurriculumReadinessService:
    """Documents-owned curriculum readiness check."""

    def test_ready_curriculum(self, db_session):
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()
        doc_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Ready CS Curriculum",
            program="BSCS",
            processing_status="PROCESSED",
        )
        _add_chunk(db_session, document_id=doc_id, source_type="curriculum")

        with patch(
            "server.modules.documents.curriculum.service.check_chroma_availability",
            return_value=True,
        ):
            readiness = check_curriculum_readiness(doc_id, "BSCS", db_session)
            assert readiness.is_ready is True

    def test_legacy_faculty_row_excluded(self, db_session):
        faculty = create_user(
            db_session,
            name="Faculty",
            email="faculty@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()
        doc_id = _add_doc(
            db_session,
            owner_id=faculty.user_id,
            source_type="curriculum",
            title="Faculty CS Curriculum",
            program="BSCS",
            processing_status="PROCESSED",
        )
        _add_chunk(db_session, document_id=doc_id, source_type="curriculum")

        with patch(
            "server.modules.documents.curriculum.service.check_chroma_availability",
            return_value=True,
        ):
            readiness = check_curriculum_readiness(doc_id, "BSCS", db_session)
            assert readiness.is_ready is False
            assert "administrator" in readiness.reason.lower()

    def test_stale_chroma_stored_flag_fails_readiness(self, db_session):
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()
        doc_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Stale Chroma Curriculum",
            program="BSCS",
            processing_status="PROCESSED",
        )
        _add_chunk(
            db_session,
            document_id=doc_id,
            source_type="curriculum",
            chroma_stored=True,
        )

        with patch(
            "server.modules.documents.curriculum.service.check_chroma_availability",
            return_value=False,
        ):
            readiness = check_curriculum_readiness(doc_id, "BSCS", db_session)
            assert readiness.is_ready is False
            assert "chroma" in readiness.reason.lower()

    def test_empty_chunks_fails_readiness(self, db_session):
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()
        doc_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="No Chunks Curriculum",
            program="BSCS",
            processing_status="PROCESSED",
        )

        with patch(
            "server.modules.documents.curriculum.service.check_chroma_availability",
            return_value=True,
        ):
            readiness = check_curriculum_readiness(doc_id, "BSCS", db_session)
            assert readiness.is_ready is False
            assert "chunks" in readiness.reason.lower()

    def test_program_mismatch_fails_readiness(self, db_session):
        admin = create_user(
            db_session,
            name="Admin",
            email="admin@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()
        doc_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="BSCS Curriculum",
            program="BSCS",
            processing_status="PROCESSED",
        )
        _add_chunk(db_session, document_id=doc_id, source_type="curriculum")

        readiness = check_curriculum_readiness(doc_id, "BSInfoTech", db_session)
        assert readiness.is_ready is False
        assert "match" in readiness.reason.lower()


class TestCurriculumSuggestionEndpoint:
    """Curriculum suggestion read model with masked validation order."""

    def test_masked_target_validation_order(self, client, db_session):
        faculty1 = create_user(
            db_session,
            name="Faculty 1",
            email="f1@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        faculty2 = create_user(
            db_session,
            name="Faculty 2",
            email="f2@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        admin = create_user(
            db_session,
            name="Admin",
            email="a@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.ADMIN,
        )
        db_session.commit()

        foreign_slm_id = _add_doc(
            db_session,
            owner_id=faculty2.user_id,
            source_type="slm",
            title="Foreign SLM",
            program="BSCS",
        )
        syllabus_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="syllabus",
            title="Shared Syllabus",
            program="BSCS",
        )
        missing_id = uuid.uuid4()

        _login(client, faculty1.email)

        # 1. Missing document -> 404 (before program check)
        resp1 = client.get(
            f"/api/v1/documents/{missing_id}/curriculum-suggestion?program=INVALID"
        )
        assert resp1.status_code == 404

        # 2. Foreign SLM -> 404 (before program check)
        resp2 = client.get(
            f"/api/v1/documents/{foreign_slm_id}/curriculum-suggestion?program=INVALID"
        )
        assert resp2.status_code == 404

        # 3. Non-SLM document -> 404 (before program check)
        resp3 = client.get(
            f"/api/v1/documents/{syllabus_id}/curriculum-suggestion?program=INVALID"
        )
        assert resp3.status_code == 404

    def test_program_validation_after_target_verified(self, client, db_session):
        faculty = create_user(
            db_session,
            name="Faculty",
            email="f@lspu.edu.ph",
            password=_TEST_PASSWORD,
            role=UserRole.FACULTY,
        )
        db_session.commit()
        slm_id = _add_doc(
            db_session,
            owner_id=faculty.user_id,
            source_type="slm",
            title="Owned SLM",
            program="BSCS",
        )
        _login(client, faculty.email)

        resp = client.get(
            f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=INVALID_PROG"
        )
        assert resp.status_code == 422

    def test_suggestion_returns_ready_and_unavailable_lists(self, client, db_session):
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

        slm_id = _add_doc(
            db_session,
            owner_id=faculty.user_id,
            source_type="slm",
            title="My SLM",
            program="BSCS",
        )

        ready_curr_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Ready BSCS Curriculum",
            program="BSCS",
            processing_status="PROCESSED",
        )
        _add_chunk(db_session, document_id=ready_curr_id, source_type="curriculum")

        unready_curr_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Processing BSCS Curriculum",
            program="BSCS",
            processing_status="PROCESSING",
        )

        def mock_chroma(doc_id, src_type):
            return str(doc_id) == str(ready_curr_id)

        _login(client, faculty.email)
        with patch(
            "server.modules.documents.curriculum.service.check_chroma_availability",
            side_effect=mock_chroma,
        ):
            resp = client.get(
                f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=BSCS"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == str(slm_id)
        assert data["selected_program"] == "BSCS"
        assert data["preferred_suggestion"] is None

        ready_ids = [item["document_id"] for item in data["curriculum_suggestions"]]
        assert str(ready_curr_id) in ready_ids

        unready_ids = [item["document_id"] for item in data["unavailable_curricula"]]
        assert str(unready_curr_id) in unready_ids

    def test_suggestion_excludes_legacy_faculty_curriculum_entirely(
        self, client, db_session
    ):
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

        slm_id = _add_doc(
            db_session,
            owner_id=faculty.user_id,
            source_type="slm",
            title="Faculty SLM",
            program="BSCS",
        )

        # Admin-uploaded curriculum (unready) -> should appear in unavailable_curricula
        admin_unready_id = _add_doc(
            db_session,
            owner_id=admin.user_id,
            source_type="curriculum",
            title="Admin Unready Curriculum",
            program="BSCS",
            processing_status="PROCESSING",
        )

        # Faculty-uploaded curriculum (legacy row) -> should NOT appear anywhere
        legacy_faculty_curr_id = _add_doc(
            db_session,
            owner_id=faculty.user_id,
            source_type="curriculum",
            title="Legacy Faculty Curriculum",
            program="BSCS",
            processing_status="PROCESSED",
        )
        _add_chunk(
            db_session, document_id=legacy_faculty_curr_id, source_type="curriculum"
        )

        _login(client, faculty.email)
        with patch(
            "server.modules.documents.curriculum.service.check_chroma_availability",
            return_value=True,
        ):
            resp = client.get(
                f"/api/v1/documents/{slm_id}/curriculum-suggestion?program=BSCS"
            )

        assert resp.status_code == 200
        data = resp.json()

        all_suggested_ids = [
            item["document_id"]
            for item in data["curriculum_suggestions"] + data["unavailable_curricula"]
        ]
        assert str(admin_unready_id) in all_suggested_ids
        assert str(legacy_faculty_curr_id) not in all_suggested_ids
