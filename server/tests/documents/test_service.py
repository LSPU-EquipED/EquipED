"""Documents service tests — in-memory helpers, sanitize, and cleanup."""

from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from server.modules.auth.models import User
from server.modules.documents.exceptions import DocumentNotFoundError
from server.modules.documents.schemas import DocumentChunkData, DocumentResponse
from server.modules.documents.service import (
    _MEM_CHUNKS,
    _MEM_DOCUMENT_OWNERS,
    _MEM_DOCUMENTS,
    _cleanup_failed_upload,
    _sanitize_error,
    create_document,
    get_document,
    list_documents,
)


# ---------------------------------------------------------------------------
# In-memory ownership / chunk ordering
# ---------------------------------------------------------------------------

def test_in_memory_documents_respect_ownership_scoping() -> None:
    doc_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    document = DocumentResponse(
        document_id=doc_id,
        title='Memory Doc',
        source_type='slm',
        processing_status='PROCESSED',
        has_ocr_pages=False,
        uploaded_at=datetime.now(UTC),
        uploaded_by=owner_id,
    )
    _MEM_DOCUMENTS[doc_id] = document
    _MEM_DOCUMENT_OWNERS[doc_id] = owner_id

    owner_view = list_documents(None, None, 1, 20, owner_id, 'faculty', db=None)
    assert owner_view.total == 1
    assert owner_view.items[0].document_id == doc_id

    other_view = list_documents(None, None, 1, 20, other_id, 'admin', db=None)
    assert other_view.total == 0
    assert other_view.items == []

    assert get_document(doc_id, owner_id, 'faculty', db=None).document_id == doc_id
    with pytest.raises(DocumentNotFoundError):
        get_document(doc_id, other_id, 'faculty', db=None)

    _MEM_DOCUMENTS.clear()
    _MEM_DOCUMENT_OWNERS.clear()


def test_get_document_returns_chunks_ordered_by_page_for_owner() -> None:
    doc_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    document = DocumentResponse(
        document_id=doc_id,
        title='Chunked Memory Doc',
        source_type='slm',
        processing_status='PROCESSED',
        has_ocr_pages=False,
        uploaded_at=datetime.now(UTC),
        uploaded_by=owner_id,
    )
    _MEM_DOCUMENTS[doc_id] = document
    _MEM_DOCUMENT_OWNERS[doc_id] = owner_id
    _MEM_CHUNKS[doc_id] = [
        DocumentChunkData(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            source_type='slm',
            agent_domain='all',
            page_number=2,
            text='page two text',
            token_count=3,
            is_ocr=False,
        ),
        DocumentChunkData(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            source_type='slm',
            agent_domain='all',
            page_number=1,
            text='page one text',
            token_count=3,
            is_ocr=False,
        ),
    ]

    response = get_document(doc_id, owner_id, 'faculty', db=None)

    assert [chunk.document_id for chunk in response.chunks] == [doc_id, doc_id]
    assert [chunk.page_number for chunk in response.chunks] == [1, 2]
    assert [chunk.text for chunk in response.chunks] == [
        'page one text',
        'page two text',
    ]

    _MEM_CHUNKS.clear()
    _MEM_DOCUMENTS.clear()
    _MEM_DOCUMENT_OWNERS.clear()


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
        '/api/v1/auth/login',
        json={'email': seeded_user.email, 'password': 'correct-horse-battery'},
    )
    assert login_response.status_code == 200

    # Upload a PDF that will fail extraction (not a real PDF structure)
    response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('broken.pdf', b'not-a-real-pdf-content', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Broken Document',
            'program': 'bsit',
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data['processing_status'] == 'FAILED'
    assert data['error_message'] is not None
    assert len(data['error_message']) > 0


def test_failed_upload_cleans_up_orphaned_file(
    client: TestClient,
    seeded_user: User,
) -> None:
    """Verify that when document processing fails, the uploaded file is removed."""
    login_response = client.post(
        '/api/v1/auth/login',
        json={'email': seeded_user.email, 'password': 'correct-horse-battery'},
    )
    assert login_response.status_code == 200

    # Upload a PDF that will fail extraction
    response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('broken.pdf', b'not-a-real-pdf-content', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Broken Document',
            'program': 'bsit',
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data['processing_status'] == 'FAILED'

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
        '/api/v1/auth/login',
        json={'email': seeded_user.email, 'password': 'correct-horse-battery'},
    )
    assert login_response.status_code == 200

    response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('broken.pdf', b'not-a-real-pdf-content', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Broken Document',
            'program': 'bsit',
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data['processing_status'] == 'FAILED'
    error_msg = data.get('error_message', '')
    assert error_msg is not None
    # Should not contain internal filesystem paths
    assert '/Volumes' not in error_msg
    assert '/tmp/' not in error_msg
    assert '/uploads/' not in error_msg


# ---------------------------------------------------------------------------
# Service-layer: document reprocessing and chunk persistence
# ---------------------------------------------------------------------------

def test_existing_documents_are_not_auto_reprocessed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from io import BytesIO
    from fastapi import UploadFile
    from server.modules.documents.service import (
        _MEM_CHUNKS,
        _MEM_DOCUMENTS,
        create_document,
    )
    from server.modules.documents.schemas import DocumentChunkData

    existing_id = uuid.uuid4()
    _MEM_DOCUMENTS.clear()
    _MEM_CHUNKS.clear()
    _MEM_CHUNKS[existing_id] = [DocumentChunkData(
        chunk_id=uuid.uuid4(),
        document_id=existing_id,
        source_type="slm",
        agent_domain="all",
        page_number=1,
        text="existing chunk",
        token_count=2,
        is_ocr=False,
    )]

    captured_calls: list[str] = []

    def fake_ingest_document(
        file_path: str,
        source_type: str,
        document_id: str,
    ) -> list[DocumentChunkData]:
        captured_calls.append(document_id)
        return [DocumentChunkData(
            chunk_id=uuid.uuid4(),
            document_id=uuid.UUID(document_id),
            source_type=source_type,
            agent_domain="all",
            page_number=1,
            text="new chunk",
            token_count=2,
            is_ocr=False,
        )]

    monkeypatch.setattr("server.modules.documents.service.UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(
        "server.modules.documents.service.ingest_document",
        fake_ingest_document,
    )
    monkeypatch.setattr(
        "server.modules.documents.service._refresh_tfidf_if_needed",
        lambda _: None,
    )

    upload = UploadFile(filename="new.pdf", file=BytesIO(b"%PDF-1.4\nnew"))
    result = create_document(
        file=upload,
        source_type="slm",
        title="New Document",
        course_title=None,
        lesson_title=None,
        program="bsit",
        uploaded_by=uuid.uuid4(),
        db=None,
    )

    assert captured_calls == [str(result.document_id)]
    assert existing_id in _MEM_CHUNKS
    assert _MEM_CHUNKS[existing_id][0].text == "existing chunk"


def test_persist_chunks_handles_empty_chunk_data(db_session) -> None:
    from server.modules.documents.service import (
        _MEM_CHUNKS,
        _persist_chunks,
    )
    from server.modules.documents.models import DocumentChunk

    document_id = uuid.uuid4()

    _persist_chunks(db_session, document_id, [])

    assert _MEM_CHUNKS[document_id] == []
    assert db_session.query(DocumentChunk).count() == 0
