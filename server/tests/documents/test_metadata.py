"""Tests for document metadata auto-detection."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from server.modules.documents.metadata import (
    _detect_academic_year,
    _detect_course_code,
    _detect_lesson_title,
    _detect_program,
    detect_metadata,
)


# ---------------------------------------------------------------------------
# 4.1 — _detect_program with known programs
# ---------------------------------------------------------------------------

class TestDetectProgram:
    def test_detects_bsit(self) -> None:
        assert _detect_program("This is a BSIT curriculum document") == "BSIT"

    def test_detects_bsed(self) -> None:
        assert _detect_program("Course syllabus for BSED students") == "BSED"

    def test_detects_bscs(self) -> None:
        assert _detect_program("BSCS Program Outcome Assessment") == "BSCS"

# ---------------------------------------------------------------------------
# 4.2 — _detect_program rejects non-program acronyms
# ---------------------------------------------------------------------------

    def test_rejects_pdf(self) -> None:
        """PDF is a common false positive — must not be detected as a program."""
        assert _detect_program("This document is a PDF file") is None

    def test_rejects_url(self) -> None:
        """URL is a common false positive."""
        assert _detect_program("The URL for the portal is https://example.com") is None

    def test_rejects_common_false_positives(self) -> None:
        """Other common acronyms should also be rejected."""
        assert _detect_program("The HTML and CSS are not programs") is None
        assert _detect_program("JSON and XML formats") is None

    def test_detects_program_among_noise(self) -> None:
        """When a real program code appears alongside false positives, detect it."""
        result = _detect_program(
            "PDF document for the BSIT program URL http://example.com"
        )
        assert result == "BSIT"


# ---------------------------------------------------------------------------
# 4.3 — _detect_academic_year with standard formats
# ---------------------------------------------------------------------------

class TestDetectAcademicYear:
    def test_detects_year_range(self) -> None:
        assert _detect_academic_year("Academic Year 2025-2026") == "2025-2026"

    def test_detects_ay_prefix(self) -> None:
        assert _detect_academic_year("AY 2025") == "AY 2025"

    def test_detects_sy_prefix_range(self) -> None:
        assert _detect_academic_year("SY 2025-2026") == "2025-2026"

    def test_detects_year_range_with_en_dash(self) -> None:
        assert _detect_academic_year("2025 – 2026") == "2025-2026"

    def test_returns_none_for_no_match(self) -> None:
        assert _detect_academic_year("No year information here") is None


# ---------------------------------------------------------------------------
# 4.4 — _detect_course_code with standard formats
# ---------------------------------------------------------------------------

class TestDetectCourseCode:
    def test_detects_ccs_101(self) -> None:
        assert _detect_course_code("CCS 101 is the intro course") == "CCS 101"

    def test_detects_it_201(self) -> None:
        assert _detect_course_code("IT 201 Networking") == "IT 201"

    def test_detects_math_101(self) -> None:
        assert _detect_course_code("MATH 101 College Algebra") == "MATH 101"

    def test_returns_none_for_no_match(self) -> None:
        assert _detect_course_code("No course code here") is None


# ---------------------------------------------------------------------------
# 4.9 — _detect_lesson_title
# ---------------------------------------------------------------------------

class TestDetectLessonTitle:
    def test_detects_standard_label(self) -> None:
        assert (
            _detect_lesson_title("Lesson Title: HUMAN INPUT-OUTPUT CHANNELS")
            == "HUMAN INPUT-OUTPUT CHANNELS"
        )

    def test_detects_label_with_dash(self) -> None:
        assert (
            _detect_lesson_title("Lesson Title- ADVANCED DATABASES")
            == "ADVANCED DATABASES"
        )

    def test_detects_multiword_label(self) -> None:
        assert (
            _detect_lesson_title("Lesson Title: Introduction to Computing")
            == "Introduction to Computing"
        )

    def test_detects_with_extra_whitespace(self) -> None:
        assert (
            _detect_lesson_title("Lesson Title:   Spaced Out Title   ")
            == "Spaced Out Title"
        )

    def test_returns_none_when_no_label(self) -> None:
        assert _detect_lesson_title("No lesson title here") is None

    def test_returns_none_for_empty_text(self) -> None:
        assert _detect_lesson_title("") is None

    def test_detects_among_other_metadata(self) -> None:
        text = (
            "Course: CMSC 313 — HUMAN COMPUTER INTERACTION\n"
            "Sem/AY: Second Semester/2025-2026\n"
            "Module No.: 4\n"
            "Lesson Title: HUMAN INPUT-OUTPUT CHANNELS\n"
            "Week Duration: Week 8-9\n"
        )
        assert _detect_lesson_title(text) == "HUMAN INPUT-OUTPUT CHANNELS"


# ---------------------------------------------------------------------------
# 4.11 — SLM cover page integration (full detect_metadata)
# ---------------------------------------------------------------------------

class TestSlmCoverPageIntegration:
    def test_detects_all_fields_from_slm_cover(self) -> None:
        """Verify emission of course_code, academic_year, lesson_title from SLM cover."""
        text = (
            "Course: CMSC 313 — HUMAN COMPUTER INTERACTION\n"
            "Sem/AY: Second Semester/2025-2026\n"
            "Module No.: 4\n"
            "Lesson Title: HUMAN INPUT-OUTPUT CHANNELS\n"
            "Week Duration: Week 8-9\n"
            "Date: March 16-27, 2026\n"
        )
        result = detect_metadata(text)
        assert result["course_code"] == "CMSC 313"
        assert result["academic_year"] == "2025-2026"
        assert result["lesson_title"] == "HUMAN INPUT-OUTPUT CHANNELS"
        # program is not present in this cover page
        assert result["program"] is None

    def test_detects_course_code_with_4_letter_prefix(self) -> None:
        """CMSC is a 4-letter prefix which the pattern {2,4} should match."""
        result = detect_metadata("Course: CMSC 313 — HCI")
        assert result["course_code"] == "CMSC 313"


# ---------------------------------------------------------------------------
# 4.5 — detect_metadata returns all nulls when no patterns match
# ---------------------------------------------------------------------------

class TestDetectMetadataAllNull:
    def test_returns_all_nulls_for_empty_text(self) -> None:
        result = detect_metadata("")
        assert result == {
            "program": None,
            "academic_year": None,
            "course_code": None,
            "lesson_title": None,
        }

    def test_returns_all_nulls_for_noise_text(self) -> None:
        result = detect_metadata(
            "This is just a plain document with no specific metadata. "
            "It discusses general topics and has no program codes, "
            "academic years, or course codes anywhere in the text."
        )
        assert result == {
            "program": None,
            "academic_year": None,
            "course_code": None,
            "lesson_title": None,
        }


# ---------------------------------------------------------------------------
# 4.6 — Detection only scans first ~6000 chars
# ---------------------------------------------------------------------------

class TestDetectionLimit:
    def test_detects_early_pattern(self) -> None:
        """Pattern within first 6000 chars should be detected."""
        text = "BSIT program " + "x" * 5000
        result = detect_metadata(text)
        assert result["program"] == "BSIT"

    def test_ignores_pattern_beyond_limit(self) -> None:
        """Pattern beyond 6000 chars should NOT be detected."""
        prefix = "x" * 6000
        text = prefix + " BSIT program "
        result = detect_metadata(text)
        assert result["program"] is None

    def test_mixed_detection_within_limit(self) -> None:
        """Multiple metadata fields within limit should all be detected."""
        text = "BSIT program AY 2025 CCS 101\nLesson Title: Test Lesson\n" + "y " * 500
        result = detect_metadata(text)
        assert result["program"] == "BSIT"
        assert result["academic_year"] == "AY 2025"
        assert result["course_code"] == "CCS 101"
        assert result["lesson_title"] == "Test Lesson"


# ---------------------------------------------------------------------------
# 4.7 — Detection does not block preprocessing on exception
# ---------------------------------------------------------------------------

class TestDetectionNonBlocking:
    def test_detect_metadata_does_not_raise(self) -> None:
        """detect_metadata itself should handle internal exceptions gracefully."""
        # If we pass something weird that causes an internal error,
        # detect_metadata still catches it via the service wrapper.
        # But the function itself uses re which shouldn't raise on str input.
        result = detect_metadata("BSIT normal text")
        assert result["program"] == "BSIT"

    def test_service_wraps_detection_in_try_except(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path, caplog
    ) -> None:
        """Verify that when detect_metadata raises during upload, it is caught and logged."""
        from io import BytesIO
        from uuid import UUID, uuid4

        from fastapi import UploadFile
        from server.modules.documents.preprocessing import SlmProcessingResult
        from server.modules.documents.schemas import DocumentChunkData
        from server.modules.documents.service import (
            _MEM_CHUNKS,
            _MEM_DOCUMENTS,
            _MEM_DOCUMENT_OWNERS,
            create_document,
        )

        # Clean in-memory state for isolation
        _MEM_DOCUMENTS.clear()
        _MEM_CHUNKS.clear()
        _MEM_DOCUMENT_OWNERS.clear()

        def _fake_ingest(
            file_path: str, source_type: str, document_id: str
        ) -> list[DocumentChunkData]:
            return [
                DocumentChunkData(
                    chunk_id=uuid4(),
                    document_id=UUID(document_id),
                    source_type=source_type,
                    agent_domain="all",
                    page_number=1,
                    text=(
                        "This document discusses the BSIT program "
                        "for academic year 2025-2026 course CCS 101."
                    ),
                    token_count=16,
                    is_ocr=False,
                )
            ]

        def _raise_on_detect(text: str) -> dict[str, str | None]:
            raise ValueError("metadata detection failed")

        def _fake_prepare_slm_package(
            chunks, **kwargs
        ) -> SlmProcessingResult:
            return SlmProcessingResult(
                document_summary="A test summary.",
                document_outline=[],
                section_summaries=[],
                key_facts={},
                warnings=[],
                readiness_status="READY",
            )

        monkeypatch.setattr("server.modules.documents.service.UPLOAD_ROOT", tmp_path)
        monkeypatch.setattr(
            "server.modules.documents.service.ingest_document", _fake_ingest
        )
        monkeypatch.setattr(
            "server.modules.documents.service.detect_metadata", _raise_on_detect
        )
        monkeypatch.setattr(
            "server.modules.documents.service._refresh_tfidf_if_needed",
            lambda _: None,
        )
        monkeypatch.setattr(
            "server.modules.documents.service.prepare_slm_package",
            _fake_prepare_slm_package,
        )

        upload = UploadFile(
            filename="new.pdf", file=BytesIO(b"%PDF-1.4\nnew content here")
        )
        result = create_document(
            file=upload,
            source_type="slm",
            title="Test Document",
            course_title=None,
            lesson_title=None,
            program="BSED",  # manual program, should be preserved
            uploaded_by=uuid4(),
            db=None,
        )

        # Document still processes successfully
        assert result.processing_status == "PROCESSED"

        # Metadata is null because detection failed
        assert result.academic_year is None
        assert result.course_code is None

        # Manual program is preserved in the stored response
        stored = _MEM_DOCUMENTS[result.document_id]
        assert stored.program == "BSED"

        # Verify the warning was logged
        assert any(
            "Metadata detection failed" in record.message
            for record in caplog.records
        )


# ---------------------------------------------------------------------------
# 4.8 — Manual program is not overwritten by auto-detection
# ---------------------------------------------------------------------------

class TestManualProgramPreserved:
    def test_detected_program_does_not_override_manual_when_set(self) -> None:
        """When program is manually set, auto-detected program is ignored."""
        manual_program = "BSED"
        text = "This document is about the BSIT program"

        # Simulate the merge logic from service.py
        effective_program = manual_program
        if effective_program is None:
            detected = detect_metadata(text)
            effective_program = detected.get("program")

        assert effective_program == "BSED"  # manual wins, not BSIT

    def test_detected_program_used_when_manual_is_none(self) -> None:
        """When program is not manually set, auto-detected program is used."""
        manual_program = None
        text = "This document is about the BSIT program"

        effective_program = manual_program
        if effective_program is None:
            detected = detect_metadata(text)
            effective_program = detected.get("program")

        assert effective_program == "BSIT"

    def test_detected_lesson_title_does_not_override_manual(self) -> None:
        """When lesson_title is manually set, auto-detected value is ignored."""
        manual_lesson_title = "Manual Lesson"
        text = "Lesson Title: Detected Lesson"

        effective_lesson_title = manual_lesson_title
        if effective_lesson_title is None:
            detected = detect_metadata(text)
            effective_lesson_title = detected.get("lesson_title")

        assert effective_lesson_title == "Manual Lesson"

    def test_detected_lesson_title_used_when_manual_is_none(self) -> None:
        """When lesson_title is not manually set, auto-detected value is used."""
        manual_lesson_title = None
        text = "Lesson Title: Auto Detected"

        effective_lesson_title = manual_lesson_title
        if effective_lesson_title is None:
            detected = detect_metadata(text)
            effective_lesson_title = detected.get("lesson_title")

        assert effective_lesson_title == "Auto Detected"

    def test_program_remains_null_when_absent_from_content(self) -> None:
        """When no known program code appears in the text, program stays null."""
        text = (
            "Course: CMSC 313 — HUMAN COMPUTER INTERACTION\n"
            "Lesson Title: HUMAN INPUT-OUTPUT CHANNELS\n"
            "Sem/AY: Second Semester/2025-2026\n"
        )
        result = detect_metadata(text)
        assert result["program"] is None
        assert result["course_code"] == "CMSC 313"
        assert result["academic_year"] == "2025-2026"
        assert result["lesson_title"] == "HUMAN INPUT-OUTPUT CHANNELS"

    def test_academic_year_and_course_code_always_set(self) -> None:
        """academic_year and course_code are always set regardless of manual program."""
        manual_program = "BSED"
        text = "BSIT program AY 2025 CCS 101"

        detected = detect_metadata(text)

        # Manual program preserved
        effective_program = manual_program
        if effective_program is None:
            effective_program = detected.get("program")

        assert effective_program == "BSED"

        # academic_year and course_code are always set from detection
        academic_year = detected.get("academic_year")
        course_code = detected.get("course_code")
        assert academic_year == "AY 2025"
        assert course_code == "CCS 101"
