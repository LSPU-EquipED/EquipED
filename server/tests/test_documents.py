"""Documents module authentication contract tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from server.modules.auth.models import User, UserRole
from server.modules.auth.service import create_user
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


def test_list_documents_requires_authenticated_session(client: TestClient) -> None:
    response = client.get('/api/v1/documents')

    assert response.status_code == 401
    assert response.json() == {'detail': 'Authentication required'}


def test_upload_document_requires_authenticated_session(client: TestClient) -> None:
    response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('sample.pdf', b'%PDF-1.4\n%auth-check', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Sample SLM',
            'program': 'bsit',
        },
    )

    assert response.status_code == 401
    assert response.json() == {'detail': 'Authentication required'}


def test_list_documents_returns_empty_inventory_for_authenticated_user(
    client: TestClient,
    seeded_user: User,
) -> None:
    login_response = client.post(
        '/api/v1/auth/login',
        json={'email': seeded_user.email, 'password': 'correct-horse-battery'},
    )

    assert login_response.status_code == 200

    response = client.get('/api/v1/documents')

    assert response.status_code == 200
    assert response.json() == {
        'items': [],
        'total': 0,
        'page': 1,
        'page_size': 20,
    }


def test_upload_document_persists_ownership(
    client: TestClient,
    seeded_user: User,
) -> None:
    """Verify that uploaded_by is set to the authenticated user."""
    login_response = client.post(
        '/api/v1/auth/login',
        json={'email': seeded_user.email, 'password': 'correct-horse-battery'},
    )
    assert login_response.status_code == 200

    response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('sample.pdf', b'%PDF-1.4\n%minimal', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Test SLM Document',
            'program': 'bsit',
        },
    )

    assert response.status_code == 201
    doc_id = response.json()['document_id']

    # Retrieve the document to verify ownership
    doc_response = client.get(f'/api/v1/documents/{doc_id}')
    assert doc_response.status_code == 200


def test_faculty_cannot_access_another_faculty_document(
    client: TestClient,
    db_session,
) -> None:
    """Verify that faculty users cannot access documents uploaded by other faculty."""
    # Create two faculty users
    faculty1 = create_user(
        db_session,
        name="Faculty One",
        email="faculty1@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    faculty2 = create_user(
        db_session,
        name="Faculty Two",
        email="faculty2@example.com",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    # Faculty1 logs in and uploads a document
    login1 = client.post(
        '/api/v1/auth/login',
        json={'email': faculty1.email, 'password': 'password123'},
    )
    assert login1.status_code == 200

    upload_response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('sample.pdf', b'%PDF-1.4\n%faculty1', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Faculty1 Document',
            'program': 'bsit',
        },
    )
    assert upload_response.status_code == 201
    doc_id = upload_response.json()['document_id']

    # Faculty1 can access their own document
    access_response = client.get(f'/api/v1/documents/{doc_id}')
    assert access_response.status_code == 200

    # Faculty2 logs in
    login2 = client.post(
        '/api/v1/auth/login',
        json={'email': faculty2.email, 'password': 'password456'},
    )
    assert login2.status_code == 200

    # Faculty2 cannot access Faculty1's document (should get 404)
    access_response = client.get(f'/api/v1/documents/{doc_id}')
    assert access_response.status_code == 404


def test_admin_can_only_access_own_documents(
    client: TestClient,
    db_session,
    seeded_user: User,
) -> None:
    """Verify that admin users are scoped to their own documents."""
    # Create a faculty user and upload a document owned by faculty.
    faculty = create_user(
        db_session,
        name="Faculty User",
        email="faculty@example.com",
        password="password789",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    # Faculty logs in and uploads a document
    login_faculty = client.post(
        '/api/v1/auth/login',
        json={'email': faculty.email, 'password': 'password789'},
    )
    assert login_faculty.status_code == 200

    upload_response = client.post(
        '/api/v1/documents/upload',
        files={'file': ('sample.pdf', b'%PDF-1.4\n%faculty', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Faculty Document',
            'program': 'bsit',
        },
    )
    assert upload_response.status_code == 201
    faculty_doc_id = upload_response.json()['document_id']

    # Admin logs in
    login_admin = client.post(
        '/api/v1/auth/login',
        json={'email': seeded_user.email, 'password': 'correct-horse-battery'},
    )
    assert login_admin.status_code == 200

    # Admin cannot access faculty-owned documents.
    access_response = client.get(f'/api/v1/documents/{faculty_doc_id}')
    assert access_response.status_code == 404

    # Admin only sees their own uploads.
    admin_upload = client.post(
        '/api/v1/documents/upload',
        files={'file': ('admin.pdf', b'%PDF-1.4\n%admin', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Admin Document',
            'program': 'bsit',
        },
    )
    assert admin_upload.status_code == 201

    list_response = client.get('/api/v1/documents')
    assert list_response.status_code == 200
    data = list_response.json()
    assert data['total'] == 1
    assert len(data['items']) == 1
    assert data['items'][0]['title'] == 'Admin Document'


def test_faculty_list_shows_only_own_documents(
    client: TestClient,
    db_session,
) -> None:
    """Verify that faculty users only see their own documents in list."""
    # Create two faculty users
    faculty1 = create_user(
        db_session,
        name="Faculty One",
        email="faculty1@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    faculty2 = create_user(
        db_session,
        name="Faculty Two",
        email="faculty2@example.com",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    # Faculty1 uploads a document
    login1 = client.post(
        '/api/v1/auth/login',
        json={'email': faculty1.email, 'password': 'password123'},
    )
    assert login1.status_code == 200

    upload1 = client.post(
        '/api/v1/documents/upload',
        files={'file': ('sample1.pdf', b'%PDF-1.4\n%doc1', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Faculty1 Doc',
            'program': 'bsit',
        },
    )
    assert upload1.status_code == 201

    # Faculty2 uploads a document
    login2 = client.post(
        '/api/v1/auth/login',
        json={'email': faculty2.email, 'password': 'password456'},
    )
    assert login2.status_code == 200

    upload2 = client.post(
        '/api/v1/documents/upload',
        files={'file': ('sample2.pdf', b'%PDF-1.4\n%doc2', 'application/pdf')},
        data={
            'source_type': 'slm',
            'title': 'Faculty2 Doc',
            'program': 'bsit',
        },
    )
    assert upload2.status_code == 201

    # Faculty2 lists documents - should only see their own
    list_response = client.get('/api/v1/documents')
    assert list_response.status_code == 200
    data = list_response.json()
    assert data['total'] == 1
    assert len(data['items']) == 1
    assert data['items'][0]['title'] == 'Faculty2 Doc'


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
    uploads_dir = Path(__file__).resolve().parent.parent.parent / "uploads"
    doc_file = uploads_dir / f"{data['document_id']}.pdf"
    assert not doc_file.exists(), f"Orphaned file should have been removed: {doc_file}"


def test_cleanup_failed_upload_removes_existing_file() -> None:
    """Verify _cleanup_failed_upload removes an existing file."""
    import tempfile

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
