"""Service-layer tests for the curriculum alignment check orchestration.

The LLM and PDF extraction are monkeypatched so these tests exercise only
the service's own orchestration logic (short-circuits, persistence,
grounding) against a real (in-memory sqlite) db_session.
"""

from __future__ import annotations

import uuid

import pytest
from server.modules.curriculum_map import service
from server.modules.curriculum_map.exceptions import (
    AlignmentCheckNotFoundError,
    CourseNotFoundError,
    NoCurriculumMapError,
)
from server.modules.curriculum_map.models import (
    Course,
    CurriculumMapCell,
    CurriculumObjective,
)
from server.modules.documents.models import Document


def _make_course_with_map(db_session) -> tuple[Course, CurriculumObjective]:
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    objective = CurriculumObjective(code="IT08", description="Teamwork", program="BSIT")
    db_session.add_all([course, objective])
    db_session.flush()
    cell = CurriculumMapCell(
        course_id=course.course_id, objective_id=objective.objective_id, level="D"
    )
    db_session.add(cell)
    db_session.commit()
    return course, objective


def _make_document(db_session) -> Document:
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/does-not-exist.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add(document)
    db_session.commit()
    return document


def test_list_courses_returns_seeded_courses(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    courses = service.list_courses(db_session)
    assert [c.course_id for c in courses] == [course.course_id]


def test_run_check_raises_when_course_not_found(db_session, monkeypatch) -> None:
    document = _make_document(db_session)
    with pytest.raises(CourseNotFoundError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=uuid.uuid4(),
            db=db_session,
        )


def test_run_check_raises_when_no_curriculum_map(db_session) -> None:
    course = Course(course_code="IT999", course_title="Unmapped", program="BSIT")
    db_session.add(course)
    db_session.commit()
    document = _make_document(db_session)

    with pytest.raises(NoCurriculumMapError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            db=db_session,
        )


def test_run_check_happy_path_persists_result(db_session, monkeypatch) -> None:
    course, objective = _make_course_with_map(db_session)
    document = _make_document(db_session)

    monkeypatch.setattr(
        service,
        "extract_document_pages",
        lambda document_id: ["Students demonstrate teamwork in a capstone project."],
    )

    class FakeClient:
        model = "fake-model"

        def generate(self, prompt: str, **_: object) -> str:
            return (
                '{"results": [{"objective_code": "IT08", "is_addressed": true, '
                '"observed_level": "D", "evidence": "Students demonstrate teamwork '
                'in a capstone project."}]}'
            )

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        db=db_session,
        llm_client=FakeClient(),
    )

    assert check.success is True
    assert check.model_name == "fake-model"
    assert check.summary == {
        "total_mapped_objectives": 1,
        "match": 1,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
    }
    assert len(check.objective_results) == 1
    result = check.objective_results[0]
    assert result["code"] == "IT08"
    assert result["status"] == "match"
    assert result["evidence_page"] == 1

    fetched = service.get_alignment_check(check.check_id, db_session)
    assert fetched.check_id == check.check_id


def test_get_alignment_check_raises_when_missing(db_session) -> None:
    with pytest.raises(AlignmentCheckNotFoundError):
        service.get_alignment_check(uuid.uuid4(), db_session)


def test_ungrounded_evidence_is_downgraded_to_not_addressed(
    db_session, monkeypatch
) -> None:
    course, objective = _make_course_with_map(db_session)
    document = _make_document(db_session)

    monkeypatch.setattr(
        service, "extract_document_pages", lambda document_id: ["Unrelated page text."]
    )

    class FakeClient:
        model = "fake-model"

        def generate(self, prompt: str, **_: object) -> str:
            return (
                '{"results": [{"objective_code": "IT08", "is_addressed": true, '
                '"observed_level": "D", "evidence": "text that does not appear '
                'in the document"}]}'
            )

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        db=db_session,
        llm_client=FakeClient(),
    )

    result = check.objective_results[0]
    assert result["status"] == "not_addressed"
    assert result["evidence_page"] is None
