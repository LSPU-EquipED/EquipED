import uuid

from fastapi.testclient import TestClient
from server.modules.auth.models import User
from server.modules.documents.models import Document, DocumentChunk


def test_outcomes_endpoint_requires_authentication(client: TestClient):
    response = client.get(f"/api/v1/documents/{uuid.uuid4()}/outcomes")
    assert response.status_code == 401


def test_authenticated_faculty_can_view_ordered_shared_syllabus_outcomes(
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
                section_ref="syllabus_outcome:CLO2",
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
                section_ref="syllabus_outcome:CLO1",
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

    response = client.get(f"/api/v1/documents/{syllabus_id}/outcomes")

    assert response.status_code == 200
    payload = response.json()
    assert [item["outcome_code"] for item in payload["outcomes"]] == ["CLO1", "CLO2"]
    assert payload["outcomes"][0]["extraction_method"] == "embedded_text"
    assert payload["outcomes"][1]["extraction_method"] == "ocr"
