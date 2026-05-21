from __future__ import annotations

from uuid import uuid4

from server.modules.documents.preprocessing import prepare_slm_package


def test_prepare_slm_package_builds_structured_context() -> None:
    chunks = [
        {
            "chunk_id": uuid4(),
            "document_id": uuid4(),
            "source_type": "slm",
            "agent_domain": "all",
            "page_number": 1,
            "text": "Learning outcomes include critical thinking and programming basics.",
            "token_count": 8,
            "is_ocr": False,
        },
        {
            "chunk_id": uuid4(),
            "document_id": uuid4(),
            "source_type": "slm",
            "agent_domain": "all",
            "page_number": 2,
            "text": "Assessment is 30% quiz and 70% exam. Data privacy applies.",
            "token_count": 10,
            "is_ocr": False,
        },
    ]

    package = prepare_slm_package(
        chunks,
        title="Intro to Programming SLM",
        course_title="Intro to Programming",
        lesson_title=None,
        program="bsit",
    )

    assert package.document_summary
    assert package.document_outline
    assert package.section_summaries
    assert package.key_facts["title"] == "Intro to Programming SLM"
    assert package.readiness_status in {"READY", "NEEDS_REVIEW"}
