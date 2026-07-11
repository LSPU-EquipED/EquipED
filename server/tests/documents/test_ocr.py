import stat
import subprocess
import uuid
from unittest.mock import patch

import pytesseract
import pytest
from server.core.config import Settings
from server.modules.documents.exceptions import (
    OcrLimitExceededError,
)
from server.modules.documents.ingestion import ingest_document
from server.modules.documents.ocr import (
    clear_ocr_validation_cache,
    perform_ocr_on_page,
    validate_ocr_installation,
)


class MockRect:
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height


class MockPage:
    def __init__(self, text: str, width: float = 612.0, height: float = 792.0):
        self.text = text
        self.rect = MockRect(width, height)

    def get_text(self) -> str:
        return self.text

    def get_pixmap(self, dpi: int = 200, colorspace: any = None, alpha: bool = False):
        class MockPixmap:
            def __init__(self):
                self.width = int(612.0 * dpi / 72)
                self.height = int(792.0 * dpi / 72)
                self.samples = b"\x00" * (self.width * self.height * 3)

        return MockPixmap()


class MockDoc:
    def __init__(self, pages: list[MockPage]):
        self.pages = pages
        self.is_encrypted = False

    def __iter__(self):
        return iter(self.pages)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture(autouse=True)
def reset_ocr_cache():
    clear_ocr_validation_cache()
    yield
    clear_ocr_validation_cache()


def test_ocr_validation_success() -> None:
    settings = Settings(tesseract_lang="eng+fil")
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng", "fil", "osd"]),
    ):
        result = validate_ocr_installation(settings)
        assert result["ready"] is True
        assert "available_languages" in result
        assert result["version"] == "4.0.0"


def test_ocr_validation_missing_lang() -> None:
    settings = Settings(tesseract_lang="eng+fil")
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
    ):
        result = validate_ocr_installation(settings)
        assert result["ready"] is False
        assert "missing required language pack" in result["detail"]


def test_ocr_validation_executable_missing() -> None:
    settings = Settings(tesseract_lang="eng+fil")
    with patch(
        "pytesseract.get_tesseract_version",
        side_effect=pytesseract.TesseractNotFoundError(),
    ):
        result = validate_ocr_installation(settings)
        assert result["ready"] is False
        assert "not found" in result["detail"]


def test_perform_ocr_on_page_success() -> None:
    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)
    page = MockPage(text="")
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string", return_value="Extracted text content"),
    ):
        outcome = perform_ocr_on_page(page, settings)
        assert outcome.is_blank is False
        assert outcome.text == "Extracted text content"


def test_perform_ocr_on_page_blank() -> None:
    settings = Settings(tesseract_lang="eng")
    page = MockPage(text="")
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string", return_value="   \n  "),
    ):
        outcome = perform_ocr_on_page(page, settings)
        assert outcome.is_blank is True
        assert outcome.text == ""


def test_perform_ocr_on_page_timeout() -> None:
    settings = Settings(tesseract_lang="eng", ocr_timeout_seconds=20)
    page = MockPage(text="")
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "pytesseract.image_to_string",
            side_effect=subprocess.TimeoutExpired("tesseract", 20),
        ),
    ):
        with pytest.raises(OcrLimitExceededError) as exc_info:
            perform_ocr_on_page(page, settings)
        assert "timed out" in str(exc_info.value)


def test_perform_ocr_on_page_limit_exceeded() -> None:
    settings = Settings(tesseract_lang="eng", ocr_max_pixels=1000)
    page = MockPage(text="", width=1000.0, height=1000.0)  # estimated pixels > 1000
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
    ):
        with pytest.raises(OcrLimitExceededError) as exc_info:
            perform_ocr_on_page(page, settings)
        assert "pixel count" in str(exc_info.value)


def test_ingest_document_scanned_success(monkeypatch) -> None:
    # Scanned document has no meaningful text
    page1 = MockPage(text="Weak overlay")  # len < 100, fails heuristic
    mock_doc = MockDoc([page1])

    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "pytesseract.image_to_string",
            return_value="Actual OCR text content that is long enough",
        ),
    ):
        chunks = ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))
        assert len(chunks) > 0
        assert chunks[0].is_ocr is True
        assert "Actual OCR text content" in chunks[0].text


def test_ingest_document_mixed_success(monkeypatch) -> None:
    # Mixed: Page 1 has meaningful selectable text, Page 2 needs OCR
    page1 = MockPage(
        text=(
            "This is page one text. It is selectable and definitely long "
            "enough to pass our heuristic text check of 100 characters "
            "and eight words."
        )
    )
    page2 = MockPage(text="Gibberish")  # needs OCR

    mock_doc = MockDoc([page1, page2])
    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "pytesseract.image_to_string",
            return_value="Page two OCR text that is also long enough",
        ),
    ):
        chunks = ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))
        # Verify chunks exist for both pages
        pages_extracted = {c.page_number for c in chunks}
        assert pages_extracted == {1, 2}

        chunk_ocr_flags = {c.page_number: c.is_ocr for c in chunks}
        assert chunk_ocr_flags[1] is False
        assert chunk_ocr_flags[2] is True


def test_ingest_document_blank_page(monkeypatch) -> None:
    # Blank page contains no selectable text, and OCR returns blank
    page1 = MockPage(text="")
    mock_doc = MockDoc([page1])

    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=2)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.get_settings", lambda: settings
    )

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch("pytesseract.image_to_string", return_value="   "),
    ):
        chunks = ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))
        assert len(chunks) == 0  # no chunks created for blank page


def test_ingest_document_ocr_limit_exceeded(monkeypatch) -> None:
    # Max OCR pages is 1, but we have 2 pages needing OCR
    page1 = MockPage(text="needs ocr")
    page2 = MockPage(text="needs ocr too")
    mock_doc = MockDoc([page1, page2])

    monkeypatch.setattr("fitz.open", lambda *args, **kwargs: mock_doc)
    monkeypatch.setattr("pathlib.Path.exists", lambda *args: True)

    settings = Settings(tesseract_lang="eng", ocr_max_pages=1)
    monkeypatch.setattr(
        "server.modules.documents.ingestion.get_settings", lambda: settings
    )

    with pytest.raises(OcrLimitExceededError) as exc_info:
        ingest_document("dummy.pdf", "slm", str(uuid.uuid4()))
    assert "exceeds the maximum limit" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Blocker 1: Readiness sanitization tests
# ---------------------------------------------------------------------------


def test_ready_route_sanitization(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from server.core.config import Settings
    from server.main import create_app

    settings = Settings(
        database_url=None,
        session_cookie_name="equiped_session",
        session_ttl_hours=24,
        tesseract_lang="eng+fil",
        environment="production",  # Make OCR required
    )

    monkeypatch.setattr("server.main.get_settings", lambda: settings)

    # Force failure with a missing language pack to test detail sanitization
    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
    ):  # missing fil
        app = create_app()
        client = TestClient(app)

        resp = client.get("/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "not_ready"

        ocr_check = data["checks"]["ocr"]
        assert ocr_check["ready"] is False
        # Detail must not expose packs, paths, or exception text.
        assert "missing required language pack(s)" not in ocr_check["detail"]
        assert ocr_check["detail"] == (
            "OCR engine is unavailable or missing required language packs."
        )


def test_ready_route_sanitization_unexpected_error(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from server.core.config import Settings
    from server.main import create_app

    settings = Settings(
        database_url=None,
        session_cookie_name="equiped_session",
        session_ttl_hours=24,
        tesseract_lang="eng+fil",
        environment="production",
    )

    monkeypatch.setattr("server.main.get_settings", lambda: settings)

    # Force an unexpected exception to leak
    with patch(
        "server.modules.documents.ocr.validate_ocr_installation",
        side_effect=PermissionError("/usr/bin/tesseract permission denied"),
    ):
        app = create_app()
        client = TestClient(app)

        resp = client.get("/ready")
        assert resp.status_code == 503
        data = resp.json()
        ocr_check = data["checks"]["ocr"]
        assert ocr_check["ready"] is False
        # Detail must not leak executable path or PermissionError details
        assert "/usr/bin" not in ocr_check["detail"]
        assert "permission denied" not in ocr_check["detail"]
        assert "PermissionError" not in ocr_check["detail"]
        assert ocr_check["detail"] == "OCR engine is unavailable or misconfigured."


# ---------------------------------------------------------------------------
# Blocker 2: Rasterization/Pillow sanitization tests
# ---------------------------------------------------------------------------


def test_rasterization_failure_raises_clean_ocr_failed_error() -> None:
    from server.modules.documents.exceptions import OcrFailedError

    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)

    # Create mock page that throws an exception during get_pixmap
    class FaultyPage(MockPage):
        def get_pixmap(
            self, dpi: int = 200, colorspace: any = None, alpha: bool = False
        ):
            raise ValueError(
                "Critical rendering context allocation failure in fitz wrapper"
            )

    page = FaultyPage(text="")

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
    ):
        with pytest.raises(OcrFailedError) as exc_info:
            perform_ocr_on_page(page, settings)

        # Verify no raw exception info is interpolated
        assert "Critical rendering" not in str(exc_info.value)
        assert "allocation failure" not in str(exc_info.value)
        assert "ValueError" not in str(exc_info.value)
        assert str(exc_info.value) == (
            "Scanned PDF page could not be read. "
            "Please check the document quality or upload a text-based PDF."
        )


def test_pillow_conversion_failure_raises_clean_ocr_failed_error() -> None:
    from server.modules.documents.exceptions import OcrFailedError

    settings = Settings(tesseract_lang="eng", ocr_dpi=200, ocr_max_pixels=8000000)

    # Mock Pillow's Image.frombytes to throw an error
    page = MockPage(text="")

    with (
        patch("pytesseract.get_tesseract_version", return_value="4.0.0"),
        patch("pytesseract.get_languages", return_value=["eng"]),
        patch(
            "PIL.Image.frombytes",
            side_effect=RuntimeError(
                "Pillow buffer underflow or invalid mode conversion"
            ),
        ),
    ):
        with pytest.raises(OcrFailedError) as exc_info:
            perform_ocr_on_page(page, settings)

        # Verify no raw exception info is interpolated
        assert "Pillow buffer" not in str(exc_info.value)
        assert "underflow" not in str(exc_info.value)
        assert "RuntimeError" not in str(exc_info.value)
        assert str(exc_info.value) == (
            "Scanned PDF page could not be read. "
            "Please check the document quality or upload a text-based PDF."
        )


# ---------------------------------------------------------------------------
# Blocker 3: Upload cleanup and recovery tests
# ---------------------------------------------------------------------------


def test_cleanup_failed_upload_retries_and_cleanup_pending(
    monkeypatch, db_session
) -> None:
    import time
    from io import BytesIO

    from fastapi import UploadFile
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.service import create_document

    # Ingestion must only begin after a durable PENDING upload intent exists.
    def fail_ingestion_after_asserting_intent(*args, **kwargs):
        intent = (
            db_session.query(Document).filter_by(title="Faulty Cleaned Document").one()
        )
        assert intent.processing_status == "PENDING"
        raise OcrLimitExceededError("Forced limit exceeded")

    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document",
        fail_ingestion_after_asserting_intent,
    )

    # Force unlink to raise OSError to exercise cleanup failure.
    unlinks_attempted = 0

    def faulty_unlink(self):
        nonlocal unlinks_attempted
        unlinks_attempted += 1
        raise OSError("Permission denied / file locked")

    monkeypatch.setattr("pathlib.Path.unlink", faulty_unlink)

    # Speed up sleep in retries
    monkeypatch.setattr(time, "sleep", lambda x: None)

    upload = UploadFile(filename="faulty.pdf", file=BytesIO(b"%PDF-1.4\nfaulty"))

    response = create_document(
        file=upload,
        source_type="slm",
        title="Faulty Cleaned Document",
        course_title=None,
        lesson_title=None,
        program="BSCS",
        uploaded_by=uuid.uuid4(),
        db=db_session,
    )

    # Deletion should have retried 3 times
    assert unlinks_attempted == 3
    # Status should be CLEANUP_PENDING
    assert response.processing_status == "CLEANUP_PENDING"

    # Confirm it is saved in DB with status CLEANUP_PENDING and no chunks are written
    db_doc = db_session.get(Document, response.document_id)
    assert db_doc is not None
    assert db_doc.processing_status == "CLEANUP_PENDING"
    assert (
        db_session.query(DocumentChunk)
        .filter_by(document_id=response.document_id)
        .count()
        == 0
    )


def test_recover_cleanup_pending_documents_success(monkeypatch, db_session) -> None:
    from pathlib import Path

    from server.modules.documents.models import Document
    from server.modules.documents.service import recover_cleanup_pending_documents

    doc_id = uuid.uuid4()
    temp_file = Path("/tmp/test_cleanup_pending_file.pdf")
    temp_file.write_bytes(b"dummy")

    # Seed a document in CLEANUP_PENDING status pointing to a file that exists
    db_doc = Document(
        document_id=doc_id,
        title="Cleanup Pending Doc",
        source_type="slm",
        file_path=str(temp_file),
        uploaded_by=uuid.uuid4(),
        processing_status="CLEANUP_PENDING",
    )
    db_session.add(db_doc)
    db_session.commit()

    assert temp_file.exists()

    # Run recovery (file path exists and is deletable)
    recovered = recover_cleanup_pending_documents(lambda: db_session)
    assert recovered == 1

    # Status should be updated to FAILED and file deleted
    db_doc_recovered = db_session.get(Document, doc_id)
    assert db_doc_recovered.processing_status == "FAILED"
    assert not temp_file.exists()


def test_recover_pending_document_upload_success(monkeypatch, db_session) -> None:
    from pathlib import Path

    from server.modules.documents.models import Document
    from server.modules.documents.service import recover_cleanup_pending_documents

    doc_id = uuid.uuid4()
    temp_file = Path("/tmp/test_pending_upload_file.pdf")
    temp_file.write_bytes(b"dummy")

    db_session.add(
        Document(
            document_id=doc_id,
            title="Interrupted Upload",
            source_type="slm",
            file_path=str(temp_file),
            uploaded_by=uuid.uuid4(),
            processing_status="PENDING",
        )
    )
    db_session.commit()

    assert recover_cleanup_pending_documents(lambda: db_session) == 1
    assert db_session.get(Document, doc_id).processing_status == "FAILED"
    assert not temp_file.exists()


def test_recover_no_database_upload_journal_removes_tracked_file(
    monkeypatch, tmp_path
) -> None:
    from server.modules.documents import service

    upload_root = tmp_path / "uploads"
    journal_root = upload_root / ".upload-journal"
    file_path = upload_root / "interrupted.pdf"
    upload_root.mkdir()
    file_path.write_bytes(b"dummy")

    monkeypatch.setattr(service, "UPLOAD_ROOT", upload_root)
    monkeypatch.setattr(service, "UPLOAD_JOURNAL_ROOT", journal_root)

    marker = service._create_upload_marker(uuid.uuid4(), file_path)

    assert service.recover_no_database_upload_journal() == 1
    assert not file_path.exists()
    assert not marker.exists()


def test_no_database_upload_marker_fsyncs_directory_entry(
    monkeypatch, tmp_path
) -> None:
    from server.modules.documents import service

    upload_root = tmp_path / "uploads"
    journal_root = upload_root / ".upload-journal"
    file_path = upload_root / "interrupted.pdf"
    upload_root.mkdir()

    monkeypatch.setattr(service, "UPLOAD_ROOT", upload_root)
    monkeypatch.setattr(service, "UPLOAD_JOURNAL_ROOT", journal_root)

    original_fsync = service.os.fsync
    fsynced_directories: list[bool] = []

    def record_fsync(descriptor: int) -> None:
        fsynced_directories.append(stat.S_ISDIR(service.os.fstat(descriptor).st_mode))
        original_fsync(descriptor)

    monkeypatch.setattr(service.os, "fsync", record_fsync)

    service._create_upload_marker(uuid.uuid4(), file_path)

    assert any(fsynced_directories)
