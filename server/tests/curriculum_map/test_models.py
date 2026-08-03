"""Model-level tests: the ORM models match the migration's table shape."""

from __future__ import annotations

import uuid

from server.modules.curriculum_map.models import (
    Course,
    CurriculumAlignmentCheck,
    CurriculumMapCell,
    CurriculumObjective,
)
from server.modules.documents.models import Document


def test_can_insert_course_objective_and_cell(db_session) -> None:
    course = Course(course_code="IT301", course_title="Data Structures", program="BSIT")
    db_session.add(course)
    db_session.flush()

    objective = CurriculumObjective(code="IT08", description="Teamwork", program="BSIT")
    db_session.add(objective)
    db_session.flush()

    cell = CurriculumMapCell(
        course_id=course.course_id, objective_id=objective.objective_id, level="D"
    )
    db_session.add(cell)
    db_session.commit()

    fetched = db_session.get(CurriculumMapCell, cell.id)
    assert fetched is not None
    assert fetched.level == "D"
    assert fetched.course_id == course.course_id


def test_blank_mapping_is_absence_of_a_row(db_session) -> None:
    course = Course(course_code="IT302", course_title="Networking", program="BSIT")
    db_session.add(course)
    db_session.commit()

    cells = (
        db_session.query(CurriculumMapCell)
        .filter(CurriculumMapCell.course_id == course.course_id)
        .all()
    )
    assert cells == []


def test_can_insert_alignment_check(db_session) -> None:
    course = Course(course_code="IT303", course_title="Algorithms", program="BSIT")
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/sample.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add_all([course, document])
    db_session.flush()

    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        model_name="test-model",
        objective_results=[{"code": "IT08", "status": "match"}],
        summary={"match": 1},
        success=True,
    )
    db_session.add(check)
    db_session.commit()

    fetched = db_session.get(CurriculumAlignmentCheck, check.check_id)
    assert fetched is not None
    assert fetched.objective_results == [{"code": "IT08", "status": "match"}]
    assert fetched.summary == {"match": 1}
