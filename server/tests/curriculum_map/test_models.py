"""Model-level tests: the ORM models match the migration's table shape."""

from __future__ import annotations

import uuid

from server.modules.alignment.curriculum.models import CurriculumAlignmentCheck
from server.modules.curriculum_map.models import (
    Course,
    CurriculumMapCell,
    CurriculumObjective,
)
from server.modules.documents.models import Document


def test_can_insert_course_objective_and_cell(db_session) -> None:
    course = Course(
        course_code="IT301", course_title="Data Structures", program="BSInfoTech"
    )
    db_session.add(course)
    db_session.flush()

    objective = CurriculumObjective(
        code="IT08", description="Teamwork", program="BSInfoTech"
    )
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
    course = Course(
        course_code="IT302", course_title="Networking", program="BSInfoTech"
    )
    db_session.add(course)
    db_session.commit()

    cells = (
        db_session.query(CurriculumMapCell)
        .filter(CurriculumMapCell.course_id == course.course_id)
        .all()
    )
    assert cells == []


def test_can_insert_alignment_check(db_session) -> None:
    course = Course(
        course_code="IT303", course_title="Algorithms", program="BSInfoTech"
    )
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


def test_alignment_check_accepts_nullable_provenance(db_session) -> None:
    course = Course(
        course_code="IT304", course_title="Provenance Test", program="BSInfoTech"
    )
    document = Document(
        title="Provenance SLM",
        source_type="slm",
        file_path="/tmp/provenance.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add_all([course, document])
    db_session.flush()

    check = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        model_name="test-model",
        objective_results=[],
        summary={},
        success=True,
        provenance={
            "model": "test-model",
            "trace_id": "trace-123",
            "grounding": {"chunk_ids": ["chunk-1"]},
        },
    )
    db_session.add(check)
    db_session.commit()

    fetched = db_session.get(CurriculumAlignmentCheck, check.check_id)
    assert fetched is not None
    assert fetched.provenance == {
        "model": "test-model",
        "trace_id": "trace-123",
        "grounding": {"chunk_ids": ["chunk-1"]},
    }

    # Without provenance the column stays NULL — no default is injected.
    bare = CurriculumAlignmentCheck(
        document_id=document.document_id,
        course_id=course.course_id,
        model_name="test-model",
        objective_results=[],
        summary={},
        success=True,
    )
    db_session.add(bare)
    db_session.commit()
    fetched_bare = db_session.get(CurriculumAlignmentCheck, bare.check_id)
    assert fetched_bare is not None
    assert fetched_bare.provenance is None


def test_models_define_hardening_indexes(db_session) -> None:
    """The ORM metadata matches the hardening migration's indexes."""
    from sqlalchemy import inspect

    inspector = inspect(db_session.get_bind())
    cell_indexes = {ix["name"] for ix in inspector.get_indexes("curriculum_map_cells")}
    assert "idx_curriculum_map_cells_course_id" in cell_indexes

    check_indexes = {
        ix["name"] for ix in inspector.get_indexes("curriculum_alignment_checks")
    }
    assert "idx_curriculum_alignment_checks_document_run_at" in check_indexes
    assert "idx_curriculum_alignment_checks_course_id" in check_indexes
