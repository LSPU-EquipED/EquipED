"""Documents router tests — auth gating and ownership scoping."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from server.modules.auth.models import User, UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk


def test_list_documents_requires_authenticated_session(client: TestClient) -> None:
    response = client.get("/api/v1/documents")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_upload_document_requires_authenticated_session(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.pdf", b"%PDF-1.4\n%auth-check", "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Sample SLM",
            "program": "BSCS",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_list_documents_returns_empty_inventory_for_authenticated_user(
    client: TestClient,
    seeded_user: User,
) -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )

    assert login_response.status_code == 200

    response = client.get("/api/v1/documents")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "stats": {
            "total": 0,
            "ready": 0,
            "processing": 0,
            "failed": 0,
        },
    }


def test_upload_document_persists_ownership(
    client: TestClient,
    seeded_user: User,
) -> None:
    """Verify that uploaded_by is set to the authenticated user."""
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )
    assert login_response.status_code == 200

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.pdf", b"%PDF-1.4\n%minimal", "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Test SLM Document",
            "program": "BSCS",
        },
    )

    assert response.status_code == 201
    doc_id = response.json()["document_id"]

    # Retrieve the document to verify ownership
    doc_response = client.get(f"/api/v1/documents/{doc_id}")
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
        email="faculty1@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    faculty2 = create_user(
        db_session,
        name="Faculty Two",
        email="faculty2@lspu.edu.ph",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    # Faculty1 logs in and uploads a document
    login1 = client.post(
        "/api/v1/auth/login",
        json={"email": faculty1.email, "password": "password123"},
    )
    assert login1.status_code == 200

    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.pdf", b"%PDF-1.4\n%faculty1", "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Faculty1 Document",
            "program": "BSCS",
        },
    )
    assert upload_response.status_code == 201
    doc_id = upload_response.json()["document_id"]

    # Faculty1 can access their own document
    access_response = client.get(f"/api/v1/documents/{doc_id}")
    assert access_response.status_code == 200

    # Faculty2 logs in
    login2 = client.post(
        "/api/v1/auth/login",
        json={"email": faculty2.email, "password": "password456"},
    )
    assert login2.status_code == 200

    # Faculty2 cannot access Faculty1's document (should get 404)
    access_response = client.get(f"/api/v1/documents/{doc_id}")
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
        email="faculty@lspu.edu.ph",
        password="password789",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    # Faculty logs in and uploads a document
    login_faculty = client.post(
        "/api/v1/auth/login",
        json={"email": faculty.email, "password": "password789"},
    )
    assert login_faculty.status_code == 200

    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.pdf", b"%PDF-1.4\n%faculty", "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Faculty Document",
            "program": "BSCS",
        },
    )
    assert upload_response.status_code == 201
    faculty_doc_id = upload_response.json()["document_id"]

    # Admin logs in
    login_admin = client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    )
    assert login_admin.status_code == 200

    # Admin cannot access faculty-owned documents.
    access_response = client.get(f"/api/v1/documents/{faculty_doc_id}")
    assert access_response.status_code == 404

    # Admin only sees their own uploads.
    admin_upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("admin.pdf", b"%PDF-1.4\n%admin", "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Admin Document",
            "program": "BSCS",
        },
    )
    assert admin_upload.status_code == 201

    list_response = client.get("/api/v1/documents")
    assert list_response.status_code == 200
    data = list_response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Admin Document"


def test_faculty_list_shows_only_own_documents(
    client: TestClient,
    db_session,
) -> None:
    """Verify that faculty users only see their own documents in list."""
    # Create two faculty users
    faculty1 = create_user(
        db_session,
        name="Faculty One",
        email="faculty1@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    faculty2 = create_user(
        db_session,
        name="Faculty Two",
        email="faculty2@lspu.edu.ph",
        password="password456",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    # Faculty1 uploads a document
    login1 = client.post(
        "/api/v1/auth/login",
        json={"email": faculty1.email, "password": "password123"},
    )
    assert login1.status_code == 200

    upload1 = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample1.pdf", b"%PDF-1.4\n%doc1", "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Faculty1 Doc",
            "program": "BSCS",
        },
    )
    assert upload1.status_code == 201

    # Faculty2 uploads a document
    login2 = client.post(
        "/api/v1/auth/login",
        json={"email": faculty2.email, "password": "password456"},
    )
    assert login2.status_code == 200

    upload2 = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample2.pdf", b"%PDF-1.4\n%doc2", "application/pdf")},
        data={
            "source_type": "slm",
            "title": "Faculty2 Doc",
            "program": "BSCS",
        },
    )
    assert upload2.status_code == 201

    # Faculty2 lists documents - should only see their own
    list_response = client.get("/api/v1/documents")
    assert list_response.status_code == 200
    data = list_response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Faculty2 Doc"


def _add_document(db_session, user_id, title: str, program: str) -> Document:
    document = Document(
        title=title,
        program=program,
        source_type="slm",
        file_path=f"/tmp/{title}.pdf",
        uploaded_by=user_id,
    )
    db_session.add(document)
    return document


def _login(client: TestClient, user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 200


def test_list_documents_rejects_unsupported_program(
    client: TestClient,
    seeded_user: User,
) -> None:
    _login(client, seeded_user)
    response = client.get("/api/v1/documents/?program=BSEd")
    assert response.status_code == 422


@pytest.mark.parametrize("program", ["BSIT", "bsinfotech"])
def test_list_documents_canonicalizes_bsit_aliases(
    client: TestClient,
    db_session,
    seeded_user: User,
    program: str,
) -> None:
    _add_document(db_session, seeded_user.user_id, "modern", "BSInfoTech")
    _add_document(db_session, seeded_user.user_id, "legacy", "BSIT")
    _add_document(db_session, seeded_user.user_id, "other", "BSCS")
    db_session.commit()
    _login(client, seeded_user)

    response = client.get(f"/api/v1/documents/?program={program}")
    assert response.status_code == 200
    assert {item["title"] for item in response.json()["items"]} == {"modern", "legacy"}


def test_list_documents_preserves_historical_program_rows(
    client: TestClient,
    db_session,
    seeded_user: User,
) -> None:
    _add_document(db_session, seeded_user.user_id, "historical", "BSN")
    db_session.commit()
    _login(client, seeded_user)

    response = client.get("/api/v1/documents/")
    assert response.status_code == 200
    assert "historical" in {item["title"] for item in response.json()["items"]}


def test_list_documents_omits_heavy_fields_while_detail_retains_them(
    client: TestClient,
    db_session,
    seeded_user: User,
) -> None:
    doc = Document(
        title="Heavy Document",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/heavy.pdf",
        uploaded_by=seeded_user.user_id,
        processing_status="PROCESSED",
        structured_summary="A large summary of the document",
        structured_outline=[{"title": "Section 1", "page": 1}],
        section_summaries=[{"title": "Section 1", "summary": "Detailed summary"}],
        key_facts={"author": "Test Author", "pages": 10},
        processing_warnings=["Warning: low resolution"],
    )
    db_session.add(doc)
    db_session.commit()

    chunk = DocumentChunk(
        document_id=doc.document_id,
        source_type="slm",
        agent_domain="sme",
        page_number=1,
        text="Sample chunk text",
        token_count=10,
    )
    db_session.add(chunk)
    db_session.commit()

    _login(client, seeded_user)

    # 1. List endpoint test
    list_resp = client.get("/api/v1/documents")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data["items"]) == 1
    item = data["items"][0]

    # Verify light fields are present
    assert item["document_id"] == str(doc.document_id)
    assert item["title"] == "Heavy Document"
    assert item["processing_status"] == "PROCESSED"

    # Verify heavy fields are omitted
    assert "structured_summary" not in item
    assert "structured_outline" not in item
    assert "section_summaries" not in item
    assert "key_facts" not in item
    assert "processing_warnings" not in item
    assert "chunks" not in item

    # 2. Detail GET endpoint test
    detail_resp = client.get(f"/api/v1/documents/{doc.document_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["structured_summary"] == "A large summary of the document"
    assert detail_data["structured_outline"] == [{"title": "Section 1", "page": 1}]
    assert detail_data["section_summaries"] == [
        {"title": "Section 1", "summary": "Detailed summary"}
    ]
    assert detail_data["key_facts"] == {"author": "Test Author", "pages": 10}
    assert detail_data["processing_warnings"] == ["Warning: low resolution"]
    assert len(detail_data["chunks"]) == 1
    assert detail_data["chunks"][0]["text"] == "Sample chunk text"


def test_list_documents_status_filtering_and_stats_bucket(
    client: TestClient,
    db_session,
    seeded_user: User,
) -> None:
    # Seed documents with ready, processing, and failed
    for title, status_val in [
        ("Doc Ready", "PROCESSED"),
        ("Doc Pending", "PENDING"),
        ("Doc Processing", "PROCESSING"),
        ("Doc Cleanup", "CLEANUP_PENDING"),
        ("Doc Failed", "FAILED"),
    ]:
        doc = Document(
            title=title,
            program="BSCS",
            source_type="slm",
            file_path=f"/tmp/{title}.pdf",
            uploaded_by=seeded_user.user_id,
            processing_status=status_val,
        )
        db_session.add(doc)
    db_session.commit()

    _login(client, seeded_user)

    # 1. No status filter -> all 5 returned, stats accurate
    resp = client.get("/api/v1/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 5
    assert data["stats"] == {
        "total": 5,
        "ready": 1,
        "processing": 3,
        "failed": 1,
    }

    # 2. Status = ready -> 1 returned, stats still independent
    resp_ready = client.get("/api/v1/documents?status=ready")
    assert resp_ready.status_code == 200
    data_ready = resp_ready.json()
    assert data_ready["total"] == 1
    assert len(data_ready["items"]) == 1
    assert data_ready["items"][0]["title"] == "Doc Ready"
    assert data_ready["stats"] == {
        "total": 5,
        "ready": 1,
        "processing": 3,
        "failed": 1,
    }

    # 3. Status = processing -> 3 returned (PENDING, PROCESSING, CLEANUP_PENDING)
    resp_proc = client.get("/api/v1/documents?status=processing")
    assert resp_proc.status_code == 200
    data_proc = resp_proc.json()
    assert data_proc["total"] == 3
    assert len(data_proc["items"]) == 3
    assert {item["title"] for item in data_proc["items"]} == {
        "Doc Pending",
        "Doc Processing",
        "Doc Cleanup",
    }
    assert data_proc["stats"] == {
        "total": 5,
        "ready": 1,
        "processing": 3,
        "failed": 1,
    }

    # 4. Status = failed -> 1 returned
    resp_failed = client.get("/api/v1/documents?status=failed")
    assert resp_failed.status_code == 200
    data_failed = resp_failed.json()
    assert data_failed["total"] == 1
    assert len(data_failed["items"]) == 1
    assert data_failed["items"][0]["title"] == "Doc Failed"
    assert data_failed["stats"] == {
        "total": 5,
        "ready": 1,
        "processing": 3,
        "failed": 1,
    }

    # 5. Invalid status -> 422
    resp_invalid = client.get("/api/v1/documents?status=invalid_status")
    assert resp_invalid.status_code == 422


def test_list_documents_search_filtering_and_wildcard_escaping(
    client: TestClient,
    db_session,
    seeded_user: User,
) -> None:
    docs = [
        Document(
            title="Introduction to 100% Python",
            course_title="Computer Science",
            course_code="CS101",
            lesson_title="Basics",
            program="BSCS",
            source_type="slm",
            file_path="/tmp/1.pdf",
            uploaded_by=seeded_user.user_id,
            processing_status="PROCESSED",
        ),
        Document(
            title="Data Structures 1000",
            course_title="Algorithms",
            course_code="CS102",
            lesson_title="Trees",
            program="BSCS",
            source_type="slm",
            file_path="/tmp/2.pdf",
            uploaded_by=seeded_user.user_id,
            processing_status="FAILED",
        ),
        Document(
            title="Web_Development_Guide",
            course_title="Web Systems",
            course_code="IT201",
            lesson_title="HTML & CSS",
            program="BSInfoTech",
            source_type="slm",
            file_path="/tmp/3.pdf",
            uploaded_by=seeded_user.user_id,
            processing_status="PROCESSED",
        ),
        Document(
            title="Web Development Guide",
            course_title="Advanced Web",
            course_code="IT202",
            lesson_title="JS Intro",
            program="BSInfoTech",
            source_type="slm",
            file_path="/tmp/4.pdf",
            uploaded_by=seeded_user.user_id,
            processing_status="PENDING",
        ),
    ]
    db_session.add_all(docs)
    db_session.commit()

    _login(client, seeded_user)

    # 1. Search literal "100%" (should NOT match "1000")
    resp_pct = client.get("/api/v1/documents?search=100%25")
    assert resp_pct.status_code == 200
    data_pct = resp_pct.json()
    assert data_pct["total"] == 1
    assert data_pct["items"][0]["title"] == "Introduction to 100% Python"
    assert data_pct["stats"]["total"] == 1
    assert data_pct["stats"]["ready"] == 1

    # 2. Search literal "Web_Development" (should NOT match "Web Development")
    resp_underscore = client.get("/api/v1/documents?search=Web_Development")
    assert resp_underscore.status_code == 200
    data_underscore = resp_underscore.json()
    assert data_underscore["total"] == 1
    assert data_underscore["items"][0]["title"] == "Web_Development_Guide"

    # 3. Search across different metadata fields
    # By course_code (case-insensitive)
    resp = client.get("/api/v1/documents?search=cs102")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["title"] == "Data Structures 1000"

    # By course_title
    resp = client.get("/api/v1/documents?search=algorithms")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["title"] == "Data Structures 1000"

    # By lesson_title
    resp = client.get("/api/v1/documents?search=basics")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["title"] == "Introduction to 100% Python"

    # Bounded & trimmed search
    resp = client.get("/api/v1/documents?search=%20%20CS101%20%20")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["title"] == "Introduction to 100% Python"

    # Base search stats before status filter
    resp = client.get("/api/v1/documents?search=CS10&status=ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Introduction to 100% Python"
    # Stats reflect CS10 base set: 1 ready, 1 failed -> total=2, ready=1, failed=1
    assert data["stats"] == {
        "total": 2,
        "ready": 1,
        "processing": 0,
        "failed": 1,
    }


def test_list_documents_pagination_and_totals(
    client: TestClient,
    db_session,
    seeded_user: User,
) -> None:
    for i in range(5):
        _add_document(db_session, seeded_user.user_id, f"Doc {i + 1}", "BSCS")
    db_session.commit()

    _login(client, seeded_user)

    p1 = client.get("/api/v1/documents?page=1&page_size=2").json()
    assert p1["total"] == 5
    assert p1["page"] == 1
    assert p1["page_size"] == 2
    assert len(p1["items"]) == 2
    assert p1["stats"]["total"] == 5

    p2 = client.get("/api/v1/documents?page=2&page_size=2").json()
    assert p2["total"] == 5
    assert p2["page"] == 2
    assert len(p2["items"]) == 2

    p3 = client.get("/api/v1/documents?page=3&page_size=2").json()
    assert p3["total"] == 5
    assert p3["page"] == 3
    assert len(p3["items"]) == 1

    p4 = client.get("/api/v1/documents?page=4&page_size=2").json()
    assert p4["total"] == 5
    assert p4["page"] == 4
    assert len(p4["items"]) == 0


def test_list_documents_ownership_scoping_and_stats(
    client: TestClient,
    db_session,
    seeded_user: User,
) -> None:
    faculty1 = create_user(
        db_session,
        name="Faculty One",
        email="f1@lspu.edu.ph",
        password="correct-horse-battery",
        role=UserRole.FACULTY,
    )
    faculty2 = create_user(
        db_session,
        name="Faculty Two",
        email="f2@lspu.edu.ph",
        password="correct-horse-battery",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    # Faculty 1 owns 2 SLMs: 1 ready, 1 failed
    doc1 = Document(
        title="F1 Ready SLM",
        source_type="slm",
        program="BSCS",
        file_path="/tmp/f1_1.pdf",
        uploaded_by=faculty1.user_id,
        processing_status="PROCESSED",
    )
    doc2 = Document(
        title="F1 Failed SLM",
        source_type="slm",
        program="BSCS",
        file_path="/tmp/f1_2.pdf",
        uploaded_by=faculty1.user_id,
        processing_status="FAILED",
    )
    # Faculty 2 owns 1 SLM (processing) + 1 shared syllabus reference (ready)
    doc3 = Document(
        title="F2 Processing SLM",
        source_type="slm",
        program="BSCS",
        file_path="/tmp/f2_1.pdf",
        uploaded_by=faculty2.user_id,
        processing_status="PROCESSING",
    )
    doc4 = Document(
        title="Shared Syllabus Reference",
        source_type="syllabus",
        program="BSCS",
        file_path="/tmp/f2_2.pdf",
        uploaded_by=faculty2.user_id,
        processing_status="PROCESSED",
    )
    db_session.add_all([doc1, doc2, doc3, doc4])
    db_session.commit()

    _login(client, faculty1)
    resp = client.get("/api/v1/documents")
    assert resp.status_code == 200
    data = resp.json()

    # Faculty 1 sees doc1 (own), doc2 (own), doc4 (shared syllabus) -> total = 3
    # doc3 (Faculty 2's SLM) is hidden!
    assert data["total"] == 3
    titles = {item["title"] for item in data["items"]}
    assert titles == {"F1 Ready SLM", "F1 Failed SLM", "Shared Syllabus Reference"}
    assert data["stats"] == {
        "total": 3,
        "ready": 2,
        "processing": 0,
        "failed": 1,
    }
