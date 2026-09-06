"""Documents service tests — in-memory helpers, sanitize, and cleanup."""

from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from server.modules.auth.models import User
from server.modules.documents import paths, persistence
from server.modules.documents.access import get_document, list_documents
from server.modules.documents.exceptions import (
    DocumentNotFoundError,
    ForbiddenUploadError,
    UnsupportedFileTypeError,
)
from server.modules.documents.journaling import _cleanup_failed_upload
from server.modules.documents.schemas import DocumentChunkData, DocumentResponse
from server.modules.documents.service import (
    _sanitize_error,
    create_document,
)


def test_paths_consumers_resolve_same_repository_root() -> None:
    """Service and journaling share the paths module's repository-root upload paths."""
    upload_root = paths.UPLOAD_ROOT
    assert upload_root.name == "uploads"
    assert paths.UPLOAD_JOURNAL_ROOT == upload_root / ".upload-journal"
    # Upload root sits directly under the repository root.
    repo_root = Path(__file__).resolve().parents[3]
    assert upload_root.parent == repo_root


def test_upload_manual_bsit_is_canonicalized(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("server.modules.documents.paths.UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document", lambda *args, **kwargs: []
    )
    result = create_document(
        UploadFile(filename="program.pdf", file=BytesIO(b"pdf")),
        "slm",
        "Program",
        None,
        None,
        "BSIT",
        uuid.uuid4(),
        db=None,
    )
    assert persistence._MEM_DOCUMENTS[result.document_id].program == "BSInfoTech"


def test_upload_unsupported_program_rejected_before_processing(
    monkeypatch, tmp_path
) -> None:
    called = False

    def ingest(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr("server.modules.documents.paths.UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr("server.modules.documents.service.ingest_document", ingest)
    with pytest.raises(UnsupportedFileTypeError, match="Only BSCS"):
        create_document(
            UploadFile(filename="program.pdf", file=BytesIO(b"pdf")),
            "slm",
            "Program",
            None,
            None,
            "BSEd",
            uuid.uuid4(),
            db=None,
        )
    assert called is False
    assert list(tmp_path.iterdir()) == []


def test_upload_rbac_precedes_unsupported_program() -> None:
    from server.modules.documents.service import _validate_upload

    with pytest.raises(ForbiddenUploadError):
        _validate_upload(
            UploadFile(filename="reference.pdf", file=BytesIO(b"pdf")),
            "syllabus",
            "BSEd",
            user_role="faculty",
        )


def test_list_documents_program_filters_keep_legacy_rows() -> None:
    persistence._MEM_DOCUMENTS.clear()
    persistence._MEM_DOCUMENT_OWNERS.clear()
    owner_id = uuid.uuid4()
    for program in ("BSInfoTech", "BSIT", "BSCS", "BSN"):
        document_id = uuid.uuid4()
        persistence._MEM_DOCUMENTS[document_id] = DocumentResponse(
            document_id=document_id,
            title=program,
            source_type="slm",
            program=program,
            processing_status="PROCESSED",
            has_ocr_pages=False,
            uploaded_at=datetime.now(UTC),
            uploaded_by=owner_id,
        )
        persistence._MEM_DOCUMENT_OWNERS[document_id] = owner_id

    def programs(value):
        return {
            item.program
            for item in list_documents(None, value, 1, 20, owner_id, "faculty").items
        }

    assert programs("bsit") == {"BSInfoTech", "BSIT"}
    assert programs("bsinfotech") == {"BSInfoTech", "BSIT"}
    assert programs("BSCS") == {"BSCS"}
    assert programs(None) == {"BSInfoTech", "BSIT", "BSCS", "BSN"}
    with pytest.raises(ValueError):
        programs("BSEd")


# ---------------------------------------------------------------------------
# In-memory ownership / chunk ordering
# ---------------------------------------------------------------------------


def test_in_memory_documents_respect_ownership_scoping() -> None:
    # Clear any leftover state from other tests
    persistence._MEM_DOCUMENTS.clear()
    persistence._MEM_DOCUMENT_OWNERS.clear()
    persistence._MEM_CHUNKS.clear()

    doc_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    document = DocumentResponse(
        document_id=doc_id,
        title="Memory Doc",
        source_type="slm",
        processing_status="PROCESSED",
        has_ocr_pages=False,
        uploaded_at=datetime.now(UTC),
        uploaded_by=owner_id,
    )
    persistence._MEM_DOCUMENTS[doc_id] = document
    persistence._MEM_DOCUMENT_OWNERS[doc_id] = owner_id

    owner_view = list_documents(None, None, 1, 20, owner_id, "faculty", db=None)
    assert owner_view.total == 1
    assert owner_view.items[0].document_id == doc_id
    assert owner_view.stats.total == 1
    assert owner_view.stats.ready == 1

    other_view = list_documents(None, None, 1, 20, other_id, "admin", db=None)
    assert other_view.total == 0
    assert other_view.items == []
    assert other_view.stats.total == 0

    assert get_document(doc_id, owner_id, "faculty", db=None).document_id == doc_id
    with pytest.raises(DocumentNotFoundError):
        get_document(doc_id, other_id, "faculty", db=None)

    persistence._MEM_DOCUMENTS.clear()
    persistence._MEM_DOCUMENT_OWNERS.clear()


def test_in_memory_list_documents_filtering_and_stats() -> None:
    persistence._MEM_DOCUMENTS.clear()
    persistence._MEM_DOCUMENT_OWNERS.clear()
    owner_id = uuid.uuid4()

    statuses = ["PROCESSED", "PENDING", "PROCESSING", "CLEANUP_PENDING", "FAILED"]
    for i, st in enumerate(statuses):
        doc_id = uuid.uuid4()
        persistence._MEM_DOCUMENTS[doc_id] = DocumentResponse(
            document_id=doc_id,
            title=f"Doc {i + 1} Course",
            course_code=f"CS10{i + 1}",
            course_title="CS Subject",
            lesson_title="Lesson Topic",
            program="BSCS",
            source_type="slm",
            processing_status=st,
            has_ocr_pages=False,
            uploaded_at=datetime.now(UTC),
            uploaded_by=owner_id,
        )
        persistence._MEM_DOCUMENT_OWNERS[doc_id] = owner_id

    # 1. Base list
    res = list_documents(None, None, 1, 20, owner_id, "faculty", db=None)
    assert res.total == 5
    assert res.stats.total == 5
    assert res.stats.ready == 1
    assert res.stats.processing == 3
    assert res.stats.failed == 1

    # 2. Status filter: processing
    proc_res = list_documents(
        None, None, 1, 20, owner_id, "faculty", status="processing", db=None
    )
    assert proc_res.total == 3
    assert len(proc_res.items) == 3
    assert proc_res.stats.total == 5
    assert proc_res.stats.ready == 1
    assert proc_res.stats.processing == 3

    # 3. Search filter
    search_res = list_documents(
        None, None, 1, 20, owner_id, "faculty", search="CS101", db=None
    )
    assert search_res.total == 1
    assert search_res.stats.total == 1
    assert search_res.stats.ready == 1

    persistence._MEM_DOCUMENTS.clear()
    persistence._MEM_DOCUMENT_OWNERS.clear()


def test_get_document_returns_chunks_ordered_by_page_for_owner() -> None:
    persistence._MEM_DOCUMENTS.clear()
    persistence._MEM_DOCUMENT_OWNERS.clear()
    persistence._MEM_CHUNKS.clear()
    doc_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    document = DocumentResponse(
        document_id=doc_id,
        title="Chunked Memory Doc",
        source_type="slm",
        processing_status="PROCESSED",
        has_ocr_pages=False,
        uploaded_at=datetime.now(UTC),
        uploaded_by=owner_id,
    )
    persistence._MEM_DOCUMENTS[doc_id] = document
    persistence._MEM_DOCUMENT_OWNERS[doc_id] = owner_id
    persistence._MEM_CHUNKS[doc_id] = [
        DocumentChunkData(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            source_type="slm",
            agent_domain="all",
            page_number=2,
            text="page two text",
            token_count=3,
            is_ocr=False,
        ),
        DocumentChunkData(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="page one text",
            token_count=3,
            is_ocr=False,
        ),
    ]

    response = get_document(doc_id, owner_id, "faculty", db=None)

    assert [chunk.document_id for chunk in response.chunks] == [doc_id, doc_id]
    assert [chunk.page_number for chunk in response.chunks] == [1, 2]
    assert [chunk.text for chunk in response.chunks] == [
        "page one text",
        "page two text",
    ]

    persistence._MEM_CHUNKS.clear()
    persistence._MEM_DOCUMENTS.clear()
    persistence._MEM_DOCUMENT_OWNERS.clear()


# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------


def test_cleanup_failed_upload_removes_existing_file() -> None:
    """Verify _cleanup_failed_upload removes an existing file."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        assert tmp_path.exists()

        _cleanup_failed_upload(tmp_path)

        assert not tmp_path.exists()


def test_cleanup_failed_upload_handles_missing_file() -> None:
    """Verify _cleanup_failed_upload does not raise when file is already gone."""
    non_existent = Path("/tmp/nonexistent_test_file_12345.pdf")
    # Should not raise
    _cleanup_failed_upload(non_existent)


# ---------------------------------------------------------------------------
# Sanitize helpers
# ---------------------------------------------------------------------------


def test_sanitize_error_strips_file_paths() -> None:
    """Verify _sanitize_error removes internal file paths."""
    raw = "File not found: /Volumes/Projects/repos/EquipED/uploads/abc123.pdf"
    result = _sanitize_error(raw)
    assert "/Volumes" not in result
    assert ".pdf" not in result
    assert result == "The uploaded file could not be processed."


def test_sanitize_error_maps_known_messages() -> None:
    """Verify known internal messages are mapped to user-friendly text."""
    assert _sanitize_error("PyMuPDF is not installed") == (
        "Document processing is unavailable. Please contact support."
    )
    assert _sanitize_error("Failed to extract document pages") == (
        "The PDF could not be read. It may be corrupted or unsupported."
    )


def test_sanitize_error_truncates_long_messages() -> None:
    """Verify excessively long error messages are truncated."""
    long_msg = "X" * 300
    result = _sanitize_error(long_msg)
    assert len(result) <= 200
    assert result.endswith("...")


# ---------------------------------------------------------------------------
# Failed upload integration tests (route + service behavior)
# ---------------------------------------------------------------------------


def test_upload_failed_processing_returns_error_message(
    client: TestClient,
    seeded_user: User,
) -> None:
    """Verify that when document processing fails, error_message is returned."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )
    assert login_response.status_code == 200

    # Upload a PDF that will fail extraction (not a real PDF structure)
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("broken.pdf", b"not-a-real-pdf-content", "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Broken Document",
            "program": "BSCS",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["processing_status"] == "FAILED"
    assert data["error_message"] is not None
    assert len(data["error_message"]) > 0


def test_failed_upload_cleans_up_orphaned_file(
    client: TestClient,
    seeded_user: User,
) -> None:
    """Verify that when document processing fails, the uploaded file is removed."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )
    assert login_response.status_code == 200

    # Upload a PDF that will fail extraction
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("broken.pdf", b"not-a-real-pdf-content", "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Broken Document",
            "program": "BSCS",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["processing_status"] == "FAILED"

    # Verify the orphaned file was cleaned up
    uploads_dir = Path(__file__).resolve().parent.parent.parent.parent / "uploads"
    doc_file = uploads_dir / f"{data['document_id']}.pdf"
    assert not doc_file.exists(), f"Orphaned file should have been removed: {doc_file}"


def test_failed_upload_error_message_is_sanitized(
    client: TestClient,
    seeded_user: User,
) -> None:
    """Verify that failed upload responses do not leak internal file paths."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )
    assert login_response.status_code == 200

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("broken.pdf", b"not-a-real-pdf-content", "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Broken Document",
            "program": "BSCS",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["processing_status"] == "FAILED"
    error_msg = data.get("error_message", "")
    assert error_msg is not None
    # Should not contain internal filesystem paths
    assert "/Volumes" not in error_msg
    assert "/tmp/" not in error_msg
    assert "/uploads/" not in error_msg


# ---------------------------------------------------------------------------
# Service-layer: document reprocessing and chunk persistence
# ---------------------------------------------------------------------------


def test_existing_documents_are_not_auto_reprocessed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from io import BytesIO

    from fastapi import UploadFile
    from server.modules.documents.schemas import DocumentChunkData
    from server.modules.documents.service import (
        create_document,
    )

    existing_id = uuid.uuid4()
    persistence._MEM_CHUNKS.clear()
    persistence._MEM_DOCUMENTS.clear()
    persistence._MEM_CHUNKS[existing_id] = [
        DocumentChunkData(
            chunk_id=uuid.uuid4(),
            document_id=existing_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="existing chunk",
            token_count=2,
            is_ocr=False,
        )
    ]

    captured_calls: list[str] = []

    def fake_ingest_document(
        file_path: str,
        source_type: str,
        document_id: str,
    ) -> list[DocumentChunkData]:
        captured_calls.append(document_id)
        return [
            DocumentChunkData(
                chunk_id=uuid.uuid4(),
                document_id=uuid.UUID(document_id),
                source_type=source_type,
                agent_domain="all",
                page_number=1,
                text="new chunk",
                token_count=2,
                is_ocr=False,
            )
        ]

    monkeypatch.setattr("server.modules.documents.paths.UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document",
        fake_ingest_document,
    )

    upload = UploadFile(filename="new.pdf", file=BytesIO(b"%PDF-1.4\nnew"))
    result = create_document(
        file=upload,
        source_type="slm",
        title="New Document",
        course_title=None,
        lesson_title=None,
        program="BSCS",
        uploaded_by=uuid.uuid4(),
        db=None,
    )

    assert captured_calls == [str(result.document_id)]
    assert existing_id in persistence._MEM_CHUNKS
    assert persistence._MEM_CHUNKS[existing_id][0].text == "existing chunk"


def test_persist_chunks_handles_empty_chunk_data(db_session) -> None:
    from server.modules.documents.models import DocumentChunk
    from server.modules.documents.persistence import _persist_chunks

    document_id = uuid.uuid4()

    _persist_chunks(db_session, document_id, [])

    assert persistence._MEM_CHUNKS[document_id] == []
    assert db_session.query(DocumentChunk).count() == 0


def test_curriculum_background_ingestion_fails_closed_on_empty_page(
    db_session, tmp_path, monkeypatch
) -> None:
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.ingestion.pipeline import ExtractedPage
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin Service Test",
        email=f"admin_failclosed_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "corrupt_curriculum.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc = Document(
        document_id=uuid.uuid4(),
        title="Corrupted Curriculum",
        source_type="curriculum",
        file_path=str(pdf_path),
        processing_status="PROCESSING",
        program="BSCS",
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    db_session.commit()

    fake_pages = [
        ExtractedPage(
            page_number=1,
            text=(
                "Curriculum Map for the Bachelor of Science in Computer Science\nPage 1"
            ),
            is_ocr=False,
        ),
        ExtractedPage(
            page_number=2,
            text="   ",
            is_ocr=False,
        ),
    ]
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline._extract_pages",
        lambda _: fake_pages,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    from server.core.config import Settings

    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc.document_id)

    db_session.expire_all()
    updated = db_session.get(Document, doc.document_id)
    assert updated.processing_status == "FAILED"

    chunks_count = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc.document_id)
        .count()
    )
    assert chunks_count == 0


def test_background_ingestion_clears_stale_chunks_on_ocr_failure(
    db_session, tmp_path, monkeypatch
) -> None:
    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.exceptions import ExtractionFailedError
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin Stale Chunk Test",
        email=f"admin_stale_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "stale_curriculum.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        title="Stale Curriculum",
        source_type="curriculum",
        file_path=str(pdf_path),
        processing_status="PROCESSING",
        program="BSCS",
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    db_session.commit()

    # Seed pre-existing / stale chunks in database and memory
    stale_chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        source_type="curriculum",
        agent_domain="all",
        page_number=1,
        text="Stale chunk text",
        token_count=3,
        is_ocr=False,
    )
    db_session.add(stale_chunk)
    db_session.commit()
    persistence._MEM_CHUNKS[doc_id] = [stale_chunk]

    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .count()
        == 1
    )

    # Force empty OCR extraction failure in ingest_document
    def fail_ingest(*args, **kwargs):
        raise ExtractionFailedError("OCR extraction produced no text for page 1")

    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document",
        fail_ingest,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc_id)

    db_session.expire_all()
    updated = db_session.get(Document, doc_id)
    assert updated.processing_status == "FAILED"

    # Verify zero persisted chunks in DB and memory
    remaining_chunks = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .count()
    )
    assert remaining_chunks == 0
    assert persistence._MEM_CHUNKS[doc_id] == []
    assert not pdf_path.exists()


def test_process_document_ingestion_expected_failure_persists_sanitized_warning(
    db_session, tmp_path, monkeypatch
) -> None:
    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.exceptions import ExtractionFailedError
    from server.modules.documents.models import Document
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin Warn Test",
        email=f"admin_warn_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "warning_doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        title="Warning Syllabus",
        source_type="syllabus",
        file_path=str(pdf_path),
        processing_status="PROCESSING",
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    db_session.commit()

    def fail_ingest(*args, **kwargs):
        raise ExtractionFailedError(
            "OCR extraction produced no text for page 2 (/var/private/secret/path.pdf)"
        )

    monkeypatch.setattr("server.modules.documents.service.ingest_document", fail_ingest)
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc_id)

    db_session.expire_all()
    updated = db_session.get(Document, doc_id)
    assert updated.processing_status == "FAILED"
    assert updated.processing_warnings is not None
    assert len(updated.processing_warnings) == 1
    warning = updated.processing_warnings[0]
    assert len(warning) <= 200
    assert "/var/private" not in warning
    assert "secret" not in warning
    assert "ExtractionFailedError" not in warning
    assert warning == (
        "Scanned PDF page could not be read. Please check the document quality "
        "or upload a text-based PDF."
    )


def test_process_document_ingestion_unexpected_failure_persists_generic_warning(
    db_session, tmp_path, monkeypatch
) -> None:
    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.models import Document
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin Generic Test",
        email=f"admin_generic_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "generic_err_doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        title="Generic Error Syllabus",
        source_type="syllabus",
        file_path=str(pdf_path),
        processing_status="PROCESSING",
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    db_session.commit()

    def unexpected_crash(*args, **kwargs):
        raise RuntimeError("Internal DB connection dropped unexpectedly: /etc/secrets")

    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document", unexpected_crash
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc_id)

    db_session.expire_all()
    updated = db_session.get(Document, doc_id)
    assert updated.processing_status == "FAILED"
    assert updated.processing_warnings == [
        "The document could not be processed due to an unexpected error."
    ]


def test_process_document_ingestion_successful_retry_clears_stale_warning(
    db_session, tmp_path, monkeypatch
) -> None:
    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.schemas import DocumentChunkData
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin Retry Test",
        email=f"admin_retry_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "retry_doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        title="Retry Doc",
        source_type="syllabus",
        file_path=str(pdf_path),
        processing_status="FAILED",
        processing_warnings=["Stale previous error message"],
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    db_session.commit()

    def successful_ingest(file_path, source_type, document_id, program=None):
        return [
            DocumentChunkData(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                source_type=source_type,
                agent_domain="all",
                page_number=1,
                text="Successful extraction chunk",
                token_count=3,
                is_ocr=True,
            )
        ]

    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document", successful_ingest
    )
    monkeypatch.setattr(
        "server.modules.documents.service.embed_document_chunks", lambda _: 1
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc_id)

    db_session.expire_all()
    updated = db_session.get(Document, doc_id)
    assert updated.processing_status == "PROCESSED"
    assert updated.processing_warnings is None
    chunks_count = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .count()
    )
    assert chunks_count == 1


def test_create_document_blank_only_fails_closed(monkeypatch, tmp_path) -> None:
    # Blank-only PDF produces empty chunk list from ingest_document
    monkeypatch.setattr("server.modules.documents.paths.UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document", lambda *args, **kwargs: []
    )
    result = create_document(
        UploadFile(filename="blank.pdf", file=BytesIO(b"%PDF-1.4\nblank")),
        "slm",
        "Blank Doc",
        None,
        None,
        "BSCS",
        uuid.uuid4(),
        db=None,
    )
    assert result.processing_status == "FAILED"
    assert result.error_message == "No extractable text was found in the uploaded PDF."
    # File should be cleaned up
    assert list(tmp_path.glob("*.pdf")) == []


def test_process_document_ingestion_initial_failure_does_not_invoke_chroma(
    db_session, tmp_path, monkeypatch
) -> None:
    from unittest.mock import MagicMock

    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.exceptions import ExtractionFailedError
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin Initial Fail",
        email=f"admin_init_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "initial_fail.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        title="Initial Fail Doc",
        source_type="syllabus",
        file_path=str(pdf_path),
        processing_status="PROCESSING",
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    db_session.commit()

    mock_chroma_delete = MagicMock()
    monkeypatch.setattr(
        "server.modules.documents.service.delete_chroma_vectors_strict",
        mock_chroma_delete,
    )

    def fail_ingest(*args, **kwargs):
        raise ExtractionFailedError("OCR extraction produced no text for page 1")

    monkeypatch.setattr("server.modules.documents.service.ingest_document", fail_ingest)
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc_id)

    # Initial failure must not invoke Chroma cleanup
    mock_chroma_delete.assert_not_called()

    db_session.expire_all()
    updated = db_session.get(Document, doc_id)
    assert updated.processing_status == "FAILED"
    assert not pdf_path.exists()
    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .count()
        == 0
    )


def test_process_document_ingestion_stale_prior_state_strict_cleanup_success(
    db_session, tmp_path, monkeypatch
) -> None:
    from unittest.mock import MagicMock

    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.exceptions import ExtractionFailedError
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin Stale Success",
        email=f"admin_stale_ok_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "stale_ok.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        title="Stale OK Doc",
        source_type="syllabus",
        file_path=str(pdf_path),
        processing_status="PROCESSING",
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    stale_chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        source_type="syllabus",
        agent_domain="all",
        page_number=1,
        text="Stale chunk text",
        token_count=3,
        is_ocr=False,
        chroma_stored=True,
    )
    db_session.add(stale_chunk)
    db_session.commit()

    mock_chroma_delete = MagicMock(return_value=True)
    monkeypatch.setattr(
        "server.modules.documents.service.delete_chroma_vectors_strict",
        mock_chroma_delete,
    )

    def fail_ingest(*args, **kwargs):
        raise ExtractionFailedError("OCR extraction produced no text for page 1")

    monkeypatch.setattr("server.modules.documents.service.ingest_document", fail_ingest)
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc_id)

    # Must invoke strict cleanup for document_id and source_type
    mock_chroma_delete.assert_called_once_with(str(doc_id), "syllabus")

    db_session.expire_all()
    updated = db_session.get(Document, doc_id)
    assert updated.processing_status == "FAILED"
    assert not pdf_path.exists()
    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .count()
        == 0
    )


def test_process_document_ingestion_stale_prior_state_missing_collection_converges(
    db_session, tmp_path, monkeypatch
) -> None:
    from unittest.mock import MagicMock

    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.exceptions import ExtractionFailedError
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin Missing Coll",
        email=f"admin_miss_coll_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "stale_missing_coll.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        title="Stale Missing Coll Doc",
        source_type="curriculum",
        file_path=str(pdf_path),
        processing_status="PROCESSING",
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    stale_chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        source_type="curriculum",
        agent_domain="all",
        page_number=1,
        text="Stale chunk text",
        token_count=3,
        is_ocr=False,
        chroma_stored=True,
    )
    db_session.add(stale_chunk)
    db_session.commit()

    mock_chroma_delete = MagicMock(return_value=False)
    monkeypatch.setattr(
        "server.modules.documents.service.delete_chroma_vectors_strict",
        mock_chroma_delete,
    )

    def fail_ingest(*args, **kwargs):
        raise ExtractionFailedError("OCR extraction produced no text for page 1")

    monkeypatch.setattr("server.modules.documents.service.ingest_document", fail_ingest)
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc_id)

    mock_chroma_delete.assert_called_once_with(str(doc_id), "curriculum")

    db_session.expire_all()
    updated = db_session.get(Document, doc_id)
    assert updated.processing_status == "FAILED"
    assert not pdf_path.exists()
    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .count()
        == 0
    )


def test_process_document_ingestion_strict_cleanup_exception_preserves_state(
    db_session, tmp_path, monkeypatch
) -> None:
    from unittest.mock import MagicMock

    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.exceptions import ExtractionFailedError
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin Cleanup Exc",
        email=f"admin_clean_exc_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "cleanup_exc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        title="Cleanup Exception Doc",
        source_type="syllabus",
        file_path=str(pdf_path),
        processing_status="PROCESSING",
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    stale_chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        source_type="syllabus",
        agent_domain="all",
        page_number=1,
        text="Stale chunk text",
        token_count=3,
        is_ocr=False,
        chroma_stored=True,
    )
    db_session.add(stale_chunk)
    db_session.commit()

    mock_chroma_delete = MagicMock(
        side_effect=RuntimeError("Chroma vectors remain after deletion: 5 leftover")
    )
    monkeypatch.setattr(
        "server.modules.documents.service.delete_chroma_vectors_strict",
        mock_chroma_delete,
    )

    mock_embed = MagicMock()
    monkeypatch.setattr(
        "server.modules.documents.service.embed_document_chunks",
        mock_embed,
    )

    def fail_ingest(*args, **kwargs):
        raise ExtractionFailedError("OCR extraction produced no text for page 1")

    monkeypatch.setattr("server.modules.documents.service.ingest_document", fail_ingest)
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc_id)

    mock_chroma_delete.assert_called_once_with(str(doc_id), "syllabus")
    # No embedding scheduled
    mock_embed.assert_not_called()

    db_session.expire_all()
    updated = db_session.get(Document, doc_id)
    assert updated.processing_status == "FAILED"
    assert updated.processing_warnings == [
        "Document processing failed and local vector cleanup could not be verified. "
        "Retry deletion when local storage is available."
    ]
    # Existing SQL chunks, chroma_stored flag, and PDF file must be preserved
    assert pdf_path.exists()
    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .count()
        == 1
    )
    remaining_chunk = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .one()
    )
    assert remaining_chunk.chroma_stored is True


def test_process_document_ingestion_no_database_mode_fails_closed_and_cleans_file(
    monkeypatch, tmp_path
) -> None:
    from server.core.config import Settings
    from server.modules.documents.service import process_document_ingestion

    monkeypatch.setattr("server.modules.documents.paths.UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url=""),
    )

    doc_id = uuid.uuid4()
    pdf_path = tmp_path / f"{doc_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake reference")

    owner_id = uuid.uuid4()
    persistence._MEM_DOCUMENTS[doc_id] = DocumentResponse(
        document_id=doc_id,
        title="No DB Reference",
        course_title="CS 101",
        lesson_title="Lesson 1",
        source_type="syllabus",
        program="BSCS",
        processing_status="PROCESSING",
        has_ocr_pages=False,
        uploaded_at=datetime.now(UTC),
        uploaded_by=owner_id,
    )
    persistence._MEM_CHUNKS[doc_id] = ["prior_chunk"]

    process_document_ingestion(doc_id)

    updated_mem = persistence._MEM_DOCUMENTS[doc_id]
    assert updated_mem.processing_status == "FAILED"
    assert updated_mem.processing_warnings == [
        "A configured database is required for reference document ingestion."
    ]
    assert persistence._MEM_CHUNKS[doc_id] == []
    assert not pdf_path.exists()

    persistence._MEM_DOCUMENTS.clear()
    persistence._MEM_CHUNKS.clear()


def test_persist_reference_stub_preserves_course_and_lesson_titles_db_and_memory(
    db_session, monkeypatch, tmp_path
) -> None:
    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.models import Document
    from server.modules.documents.service import create_document

    monkeypatch.setattr("server.modules.documents.paths.UPLOAD_ROOT", tmp_path)

    admin = create_user(
        db_session,
        name="Admin Metadata Test",
        email=f"admin_meta_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    # 1. Database path
    db_resp = create_document(
        file=UploadFile(filename="syllabus.pdf", file=BytesIO(b"%PDF-1.4\nsyllabus")),
        source_type="syllabus",
        title="Intro to Computing",
        course_title="CS 101",
        lesson_title="Week 1: Fundamentals",
        program="BSCS",
        uploaded_by=admin.user_id,
        user_role="admin",
        db=db_session,
    )
    assert db_resp.course_title == "CS 101"
    assert db_resp.lesson_title == "Week 1: Fundamentals"
    assert db_resp.processing_status == "PROCESSING"

    db_doc = db_session.get(Document, db_resp.document_id)
    assert db_doc is not None
    assert db_doc.course_title == "CS 101"
    assert db_doc.lesson_title == "Week 1: Fundamentals"

    # 2. In-memory / no-DB path
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url=""),
    )
    mem_resp = create_document(
        file=UploadFile(
            filename="curriculum.pdf", file=BytesIO(b"%PDF-1.4\ncurriculum")
        ),
        source_type="curriculum",
        title="Curriculum Mapping",
        course_title="BSCS Map",
        lesson_title="Year 1 Sequence",
        program="BSCS",
        uploaded_by=admin.user_id,
        user_role="admin",
        db=None,
    )
    assert mem_resp.course_title == "BSCS Map"
    assert mem_resp.lesson_title == "Year 1 Sequence"
    assert mem_resp.processing_status == "PROCESSING"

    mem_doc = persistence._MEM_DOCUMENTS.get(mem_resp.document_id)
    assert mem_doc is not None
    assert mem_doc.course_title == "BSCS Map"
    assert mem_doc.lesson_title == "Year 1 Sequence"

    persistence._MEM_DOCUMENTS.clear()
    persistence._MEM_DOCUMENT_OWNERS.clear()


def test_process_document_ingestion_db_write_failure_strict_cleanup_success(
    db_session, tmp_path, monkeypatch
) -> None:
    from unittest.mock import MagicMock

    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.schemas import DocumentChunkData
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin DB Write Fail Success",
        email=f"admin_dbw_ok_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "dbw_ok.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        title="DB Write Fail Doc",
        source_type="syllabus",
        file_path=str(pdf_path),
        processing_status="PROCESSING",
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    stale_chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        source_type="syllabus",
        agent_domain="all",
        page_number=1,
        text="Stale chunk text",
        token_count=3,
        is_ocr=False,
        chroma_stored=True,
    )
    db_session.add(stale_chunk)
    db_session.commit()

    mock_chroma_delete = MagicMock(return_value=True)
    monkeypatch.setattr(
        "server.modules.documents.service.delete_chroma_vectors_strict",
        mock_chroma_delete,
    )

    def successful_extract(*args, **kwargs):
        return [
            DocumentChunkData(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=1,
                text="Fresh extracted chunk",
                token_count=3,
                is_ocr=False,
            )
        ]

    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document", successful_extract
    )

    def failing_persist_chunks(*args, **kwargs):
        raise RuntimeError("Disk full / DB connection lost during chunk write")

    monkeypatch.setattr(
        "server.modules.documents.service.persistence._persist_chunks",
        failing_persist_chunks,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc_id)

    mock_chroma_delete.assert_called_once_with(str(doc_id), "syllabus")

    db_session.expire_all()
    updated = db_session.get(Document, doc_id)
    assert updated.processing_status == "FAILED"
    assert updated.processing_warnings == [
        "The document could not be processed due to an unexpected error."
    ]
    assert not pdf_path.exists()
    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .count()
        == 0
    )


def test_process_document_ingestion_db_write_fail_unverified_preserves_state(
    db_session, tmp_path, monkeypatch
) -> None:
    from unittest.mock import MagicMock

    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.schemas import DocumentChunkData
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin DB Write Fail Unverified",
        email=f"admin_dbw_unver_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    pdf_path = tmp_path / "dbw_unver.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake")

    doc_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        title="DB Write Fail Doc Unverified",
        source_type="syllabus",
        file_path=str(pdf_path),
        processing_status="PROCESSING",
        uploaded_by=admin.user_id,
    )
    db_session.add(doc)
    stale_chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        source_type="syllabus",
        agent_domain="all",
        page_number=1,
        text="Stale chunk text",
        token_count=3,
        is_ocr=False,
        chroma_stored=True,
    )
    db_session.add(stale_chunk)
    db_session.commit()

    mock_chroma_delete = MagicMock(
        side_effect=RuntimeError("Chroma vectors remain after deletion: leftover")
    )
    monkeypatch.setattr(
        "server.modules.documents.service.delete_chroma_vectors_strict",
        mock_chroma_delete,
    )

    def successful_extract(*args, **kwargs):
        return [
            DocumentChunkData(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=1,
                text="Fresh extracted chunk",
                token_count=3,
                is_ocr=False,
            )
        ]

    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document", successful_extract
    )

    def failing_persist_chunks(*args, **kwargs):
        raise RuntimeError("Disk full / DB connection lost during chunk write")

    monkeypatch.setattr(
        "server.modules.documents.service.persistence._persist_chunks",
        failing_persist_chunks,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(doc_id)

    mock_chroma_delete.assert_called_once_with(str(doc_id), "syllabus")

    db_session.expire_all()
    updated = db_session.get(Document, doc_id)
    assert updated.processing_status == "FAILED"
    assert updated.processing_warnings == [
        "Document processing failed and local vector cleanup could not be verified. "
        "Retry deletion when local storage is available."
    ]
    # State preserved for retry
    assert pdf_path.exists()
    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .count()
        == 1
    )
    remaining_chunk = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id)
        .one()
    )
    assert remaining_chunk.chroma_stored is True


def test_startup_recovery_preserves_unverified_vector_cleanup_state(
    db_session, tmp_path, monkeypatch
) -> None:
    """Startup recovery must not unlink PDFs for FAILED docs with unverified vectors.

    Ordinary FAILED documents without that exact marker must still be cleaned up.
    """
    from unittest.mock import MagicMock

    from server.core.config import Settings
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.exceptions import ExtractionFailedError
    from server.modules.documents.journaling import (
        UNVERIFIED_VECTOR_CLEANUP_WARNING,
        recover_cleanup_pending_documents,
    )
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.documents.service import process_document_ingestion

    admin = create_user(
        db_session,
        name="Admin Startup Recovery Discrim",
        email=f"admin_discrim_{uuid.uuid4().hex[:6]}@lspu.edu.ph",
        password="SecretPassword123!",
        role=UserRole.ADMIN,
    )
    db_session.commit()
    admin_id = admin.user_id

    # 1. Document with unverified vector cleanup failure
    unverified_pdf = tmp_path / "unverified.pdf"
    unverified_pdf.write_bytes(b"%PDF-1.4\nunverified")

    unverified_id = uuid.uuid4()
    doc_unverified = Document(
        document_id=unverified_id,
        title="Unverified Cleanup Doc",
        source_type="syllabus",
        file_path=str(unverified_pdf),
        processing_status="PROCESSING",
        uploaded_by=admin_id,
    )
    db_session.add(doc_unverified)
    stale_chunk = DocumentChunk(
        chunk_id=uuid.uuid4(),
        document_id=unverified_id,
        source_type="syllabus",
        agent_domain="all",
        page_number=1,
        text="Stale chunk text",
        token_count=3,
        is_ocr=False,
        chroma_stored=True,
    )
    db_session.add(stale_chunk)
    db_session.commit()

    mock_chroma_delete = MagicMock(
        side_effect=RuntimeError("Chroma vectors remain after deletion: 2 leftover")
    )
    monkeypatch.setattr(
        "server.modules.documents.service.delete_chroma_vectors_strict",
        mock_chroma_delete,
    )

    def fail_extract(*args, **kwargs):
        raise ExtractionFailedError("Corrupted scan")

    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document", fail_extract
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_session_factory",
        lambda: lambda: db_session,
    )
    monkeypatch.setattr(
        "server.modules.documents.service.get_settings",
        lambda: Settings(database_url="sqlite:///:memory:"),
    )

    process_document_ingestion(unverified_id)

    db_session.expire_all()
    unverified_after = db_session.get(Document, unverified_id)
    assert unverified_after.processing_status == "FAILED"
    assert unverified_after.processing_warnings == [UNVERIFIED_VECTOR_CLEANUP_WARNING]
    assert unverified_pdf.exists()
    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == unverified_id)
        .count()
        == 1
    )
    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == unverified_id)
        .one()
        .chroma_stored
        is True
    )

    # 2. Ordinary FAILED document without unverified vector marker
    ordinary_pdf = tmp_path / "ordinary_failed.pdf"
    ordinary_pdf.write_bytes(b"%PDF-1.4\nordinary")

    ordinary_id = uuid.uuid4()
    doc_ordinary = Document(
        document_id=ordinary_id,
        title="Ordinary Failed Doc",
        source_type="slm",
        file_path=str(ordinary_pdf),
        processing_status="FAILED",
        processing_warnings=["No extractable text was found in the uploaded PDF."],
        uploaded_by=admin_id,
    )
    db_session.add(doc_ordinary)
    db_session.commit()

    assert ordinary_pdf.exists()

    # 3. Run startup recovery
    recovered_count = recover_cleanup_pending_documents(lambda: db_session)
    assert recovered_count == 1

    # Unverified document state must remain fully preserved
    db_session.expire_all()
    unverified_final = db_session.get(Document, unverified_id)
    assert unverified_final.processing_status == "FAILED"
    assert unverified_final.processing_warnings == [UNVERIFIED_VECTOR_CLEANUP_WARNING]
    assert unverified_pdf.exists()
    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == unverified_id)
        .count()
        == 1
    )
    assert (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == unverified_id)
        .one()
        .chroma_stored
        is True
    )

    # Ordinary failed document must have had its PDF unlinked
    assert not ordinary_pdf.exists()
