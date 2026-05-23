"""Documents module authentication contract tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
