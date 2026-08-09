import uuid

from fastapi.testclient import TestClient
from server.modules.auth.models import User
from server.modules.documents.models import Document, DocumentChunk


def test_course_contents_endpoint_requires_authentication(client: TestClient):
    response = client.get(f"/api/v1/documents/{uuid.uuid4()}/course-contents")
    assert response.status_code == 401


def test_authenticated_faculty_can_view_ordered_shared_syllabus_course_contents(
    client: TestClient, db_session, seeded_user: User
):
    syllabus_id = uuid.uuid4()
    db_session.add(
        Document(
            document_id=syllabus_id,
            title="Standard Networking Syllabus",
            source_type="syllabus",
            file_path="uploads/syllabus.pdf",
            uploaded_by=seeded_user.user_id,
            processing_status="PROCESSED",
        )
    )
    db_session.add_all(
        [
            DocumentChunk(
                document_id=syllabus_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=3,
                text="Configure secure local area networks.",
                token_count=6,
                is_ocr=True,
                section_ref="syllabus_course_content:2:1",
                chunk_index=1,
                chroma_stored=True,
            ),
            DocumentChunk(
                document_id=syllabus_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=2,
                text="Explain foundational networking concepts.",
                token_count=5,
                is_ocr=False,
                section_ref="syllabus_course_content:1:1",
                chunk_index=0,
                chroma_stored=True,
            ),
        ]
    )
    db_session.commit()
    assert client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    ).status_code == 200

    response = client.get(f"/api/v1/documents/{syllabus_id}/course-contents")

    assert response.status_code == 200
    payload = response.json()
    assert [item["content_ref"] for item in payload["contents"]] == ["1:1", "2:1"]
    assert payload["contents"][0]["extraction_method"] == "embedded_text"
    assert payload["contents"][1]["extraction_method"] == "ocr"


def test_available_syllabi_lists_only_processed_references_with_contents_and_vectors(
    client: TestClient, db_session, seeded_user: User, monkeypatch
):
    ready_id = uuid.uuid4()
    missing_vectors_id = uuid.uuid4()
    db_session.add_all(
        [
            Document(
                document_id=ready_id,
                title="Ready Syllabus",
                source_type="syllabus",
                file_path="uploads/ready.pdf",
                uploaded_by=seeded_user.user_id,
                processing_status="PROCESSED",
            ),
            Document(
                document_id=missing_vectors_id,
                title="Not Indexed Syllabus",
                source_type="syllabus",
                file_path="uploads/not-indexed.pdf",
                uploaded_by=seeded_user.user_id,
                processing_status="PROCESSED",
            ),
            DocumentChunk(
                document_id=ready_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=2,
                text="Apply secure networking principles.",
                token_count=4,
                is_ocr=False,
                section_ref="syllabus_course_content:1:1",
                chunk_index=0,
                chroma_stored=True,
            ),
            DocumentChunk(
                document_id=missing_vectors_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=2,
                text="Explain networking principles.",
                token_count=3,
                is_ocr=False,
                section_ref="syllabus_course_content:1:1",
                chunk_index=0,
                chroma_stored=False,
            ),
        ]
    )
    db_session.commit()
    from server.modules.documents.syllabus import service as reference_service

    monkeypatch.setattr(
        reference_service,
        "check_chroma_availability",
        lambda document_id, _source_type: document_id == str(ready_id),
    )
    assert client.post(
        "/api/v1/auth/login",
        json={"email": seeded_user.email, "password": "correct-horse-battery"},
    ).status_code == 200

    response = client.get("/api/v1/documents/syllabi/available")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["document_id"] == str(ready_id)
    assert payload["items"][0]["content_count"] == 1
