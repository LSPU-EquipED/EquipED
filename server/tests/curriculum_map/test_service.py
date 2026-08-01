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
    DocumentAccessDeniedError,
    NoCurriculumMapError,
)
from server.modules.curriculum_map.models import (
    Course,
    CurriculumAlignmentCheck,
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


def _make_document(db_session, uploaded_by: uuid.UUID | None = None) -> Document:
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/does-not-exist.pdf",
        uploaded_by=uploaded_by or uuid.uuid4(),
    )
    db_session.add(document)
    db_session.commit()
    return document


def test_list_courses_returns_seeded_courses(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    courses = service.list_courses(db_session)
    assert [c.course_id for c in courses] == [course.course_id]


def test_run_check_raises_when_course_not_found(db_session, monkeypatch) -> None:
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    with pytest.raises(CourseNotFoundError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=uuid.uuid4(),
            current_user_id=owner,
            db=db_session,
        )


def test_run_check_raises_when_no_curriculum_map(db_session) -> None:
    course = Course(course_code="IT999", course_title="Unmapped", program="BSIT")
    db_session.add(course)
    db_session.commit()
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)

    with pytest.raises(NoCurriculumMapError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=owner,
            db=db_session,
        )


def test_run_check_raises_when_document_missing(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    with pytest.raises(DocumentAccessDeniedError):
        service.run_curriculum_alignment_check(
            document_id=uuid.uuid4(),
            course_id=course.course_id,
            current_user_id=uuid.uuid4(),
            db=db_session,
        )


def test_run_check_raises_when_not_document_owner(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)

    with pytest.raises(DocumentAccessDeniedError):
        service.run_curriculum_alignment_check(
            document_id=document.document_id,
            course_id=course.course_id,
            current_user_id=uuid.uuid4(),
            db=db_session,
        )


def test_run_check_happy_path_persists_result(db_session, monkeypatch) -> None:
    course, objective = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)

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
        current_user_id=owner,
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

    fetched = service.get_alignment_check(check.check_id, owner, db_session)
    assert fetched.check_id == check.check_id


def test_get_alignment_check_raises_when_missing(db_session) -> None:
    with pytest.raises(AlignmentCheckNotFoundError):
        service.get_alignment_check(uuid.uuid4(), uuid.uuid4(), db_session)


def test_get_alignment_check_raises_for_non_owner(db_session, monkeypatch) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    monkeypatch.setattr(
        service, "extract_document_pages", lambda document_id: ["Some content."]
    )

    class FakeClient:
        model = "fake-model"

        def generate(self, prompt: str, **_: object) -> str:
            return '{"results": []}'

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(),
    )

    with pytest.raises(DocumentAccessDeniedError):
        service.get_alignment_check(check.check_id, uuid.uuid4(), db_session)


def test_get_document_pages_raises_for_non_owner(db_session, monkeypatch) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    monkeypatch.setattr(
        service, "extract_document_pages", lambda document_id: ["Some content."]
    )

    class FakeClient:
        model = "fake-model"

        def generate(self, prompt: str, **_: object) -> str:
            return '{"results": []}'

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(),
    )

    with pytest.raises(DocumentAccessDeniedError):
        service.get_document_pages_for_check(check.check_id, uuid.uuid4(), db_session)


def test_ungrounded_evidence_is_downgraded_to_not_addressed(
    db_session, monkeypatch
) -> None:
    course, objective = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)

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
        current_user_id=owner,
        db=db_session,
        llm_client=FakeClient(),
    )

    result = check.objective_results[0]
    assert result["status"] == "not_addressed"
    assert result["evidence_page"] is None


def test_run_check_short_circuits_when_pdf_extraction_fails(
    db_session, monkeypatch
) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)

    monkeypatch.setattr(service, "extract_document_pages", lambda document_id: [])

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("LLM must not be called when PDF extraction fails")

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=type("Client", (), {"generate": _boom})(),
    )

    assert check.success is False
    assert check.error_message == "Could not extract text from the SLM PDF."
    assert check.objective_results == []
    assert check.summary == {
        "total_mapped_objectives": 1,
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
    }


def test_run_check_short_circuits_when_llm_fails(db_session, monkeypatch) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)

    monkeypatch.setattr(
        service, "extract_document_pages", lambda document_id: ["Some SLM content."]
    )

    class FailingClient:
        model = "fake-model"

        def generate(self, prompt: str, **_: object) -> str:
            return "not valid json"

    check = service.run_curriculum_alignment_check(
        document_id=document.document_id,
        course_id=course.course_id,
        current_user_id=owner,
        db=db_session,
        llm_client=FailingClient(),
    )

    assert check.success is False
    assert check.error_message == (
        "The alignment check could not complete (LLM error or invalid response)."
    )
    assert check.objective_results == []
    assert check.summary == {
        "total_mapped_objectives": 1,
        "match": 0,
        "under_developed": 0,
        "over_developed": 0,
        "not_addressed": 0,
    }


def test_cap_slm_text_leaves_short_text_untouched() -> None:
    text = "short document text"
    assert service._cap_slm_text(text) == text


def test_cap_slm_text_keeps_head_and_tail_for_long_text() -> None:
    head_marker = "HEAD-START-MARKER"
    tail_marker = "TAIL-END-MARKER"
    filler = "x" * service._MAX_SLM_TEXT_CHARS
    text = f"{head_marker}{filler}{tail_marker}"

    capped = service._cap_slm_text(text)

    assert len(capped) <= service._MAX_SLM_TEXT_CHARS + len(service._HEAD_TAIL_MARKER)
    assert head_marker in capped
    assert tail_marker in capped
    assert service._HEAD_TAIL_MARKER in capped


def test_list_checks_returns_only_current_users_checks_newest_first(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    other_owner = uuid.uuid4()

    mine_doc = _make_document(db_session, uploaded_by=owner)
    other_doc = _make_document(db_session, uploaded_by=other_owner)

    older = CurriculumAlignmentCheck(
        document_id=mine_doc.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(older)
    db_session.commit()

    newer = CurriculumAlignmentCheck(
        document_id=mine_doc.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(newer)
    db_session.commit()

    not_mine = CurriculumAlignmentCheck(
        document_id=other_doc.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(not_mine)
    db_session.commit()

    items, total = service.list_alignment_checks(
        current_user_id=owner, page=1, page_size=20, db=db_session
    )
    assert total == 2
    assert [i["check_id"] for i in items] == [newer.check_id, older.check_id]
    assert items[0]["document_title"] == "Sample SLM"
    assert items[0]["course_title"] == "Data Structures"


def test_list_checks_paginates(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)

    for _ in range(3):
        db_session.add(
            CurriculumAlignmentCheck(
                document_id=document.document_id,
                course_id=course.course_id,
                objective_results=[],
                summary={"total_mapped_objectives": 0},
                success=True,
            )
        )
        db_session.commit()

    page_1, total = service.list_alignment_checks(
        current_user_id=owner, page=1, page_size=2, db=db_session
    )
    page_2, _ = service.list_alignment_checks(
        current_user_id=owner, page=2, page_size=2, db=db_session
    )
    assert total == 3
    assert len(page_1) == 2
    assert len(page_2) == 1


def test_list_checks_returns_empty_for_user_with_none(db_session) -> None:
    items, total = service.list_alignment_checks(
        current_user_id=uuid.uuid4(), page=1, page_size=20, db=db_session
    )
    assert items == []
    assert total == 0


def test_delete_check_removes_row(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()
    check_id = check.check_id

    service.delete_alignment_check(check_id, owner, db_session)

    assert db_session.get(CurriculumAlignmentCheck, check_id) is None


def test_delete_check_raises_for_nonexistent_check(db_session) -> None:
    with pytest.raises(AlignmentCheckNotFoundError):
        service.delete_alignment_check(uuid.uuid4(), uuid.uuid4(), db_session)


def test_delete_check_raises_for_non_owner(db_session) -> None:
    course, _ = _make_course_with_map(db_session)
    owner = uuid.uuid4()
    other_user = uuid.uuid4()
    document = _make_document(db_session, uploaded_by=owner)
    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        objective_results=[],
        summary={"total_mapped_objectives": 0},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    with pytest.raises(DocumentAccessDeniedError):
        service.delete_alignment_check(check.check_id, other_user, db_session)
