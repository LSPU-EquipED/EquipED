"""Transactional administrator catalog editing and audit history."""

import uuid

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError

from .management_schemas import MappingEdit, ObjectiveInput
from .models import Course, CurriculumChange, CurriculumMapCell, CurriculumObjective
from .service import normalize_program


class CatalogError(Exception):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def objective_json(row, mapping_count=0):
    return {
        "objective_id": str(row.objective_id),
        "code": row.code,
        "description": row.description,
        "program": normalize_program(row.program),
        "version": row.version,
        "mapping_count": mapping_count,
    }


def catalog(db):
    counts = dict(
        db.query(CurriculumMapCell.objective_id, func.count())
        .group_by(CurriculumMapCell.objective_id)
        .all()
    )
    return {
        "items": [
            objective_json(row, counts.get(row.objective_id, 0))
            for row in db.query(CurriculumObjective)
            .order_by(CurriculumObjective.program, CurriculumObjective.code)
            .all()
        ]
    }


def audit(db, actor, kind, entity_id, before, after):
    db.add(
        CurriculumChange(
            actor_id=actor,
            entity_type=kind,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )


def save_objective(db, actor: uuid.UUID, data: ObjectiveInput, objective_id=None):
    try:
        before = None
        if objective_id is None:
            row = CurriculumObjective(**data.model_dump(), managed_by_admin=True)
            db.add(row)
            db.flush()
        else:
            row = (
                db.query(CurriculumObjective)
                .filter_by(objective_id=objective_id)
                .populate_existing()
                .with_for_update()
                .one_or_none()
            )
            if row is None:
                raise CatalogError("Objective not found", 404)
            before = objective_json(row)
            courses = (
                db.query(Course)
                .join(
                    CurriculumMapCell, CurriculumMapCell.course_id == Course.course_id
                )
                .filter(CurriculumMapCell.objective_id == objective_id)
                .all()
            )
            if any(
                normalize_program(course.program) != data.program for course in courses
            ):
                raise CatalogError(
                    "Remove incompatible course mappings before changing program."
                )
            result = db.execute(
                update(CurriculumObjective)
                .where(
                    CurriculumObjective.objective_id == objective_id,
                    CurriculumObjective.version == data.version,
                )
                .values(
                    **data.model_dump(exclude={"version"}),
                    version=data.version + 1,
                    managed_by_admin=True,
                )
            )
            if result.rowcount != 1:
                raise CatalogError("This objective changed. Reload it before saving.")
            db.flush()
            db.refresh(row)
        audit(db, actor, "objective", row.objective_id, before, objective_json(row))
        db.commit()
        return objective_json(
            row,
            db.query(CurriculumMapCell)
            .filter_by(objective_id=row.objective_id)
            .count(),
        )
    except IntegrityError as exc:
        db.rollback()
        raise CatalogError(
            "An objective with this code already exists for the program."
        ) from exc
    except Exception:
        db.rollback()
        raise


def course_mappings(db, course_id):
    course = db.get(Course, course_id)
    if course is None:
        raise CatalogError("Course not found", 404)
    return {
        "course_id": str(course_id),
        "version": course.mapping_version,
        "entries": [
            {"objective_id": str(cell.objective_id), "level": cell.level}
            for cell in db.query(CurriculumMapCell).filter_by(course_id=course_id).all()
        ],
    }


def save_mappings(db, actor, course_id, data: MappingEdit):
    try:
        course = db.get(Course, course_id)
        if course is None:
            raise CatalogError("Course not found", 404)
        ids = [entry.objective_id for entry in data.entries]
        if len(ids) != len(set(ids)):
            raise CatalogError("Each objective may be mapped only once.", 422)
        objectives = (
            db.query(CurriculumObjective)
            .filter(CurriculumObjective.objective_id.in_(ids))
            .order_by(CurriculumObjective.objective_id)
            .with_for_update()
            .all()
        )
        if len(objectives) != len(ids) or any(
            normalize_program(row.program) != normalize_program(course.program)
            for row in objectives
        ):
            raise CatalogError(
                "Select existing objectives from the course's program.", 422
            )
        before = course_mappings(db, course_id)
        claimed = db.execute(
            update(Course)
            .where(
                Course.course_id == course_id, Course.mapping_version == data.version
            )
            .values(mapping_version=data.version + 1, mappings_managed=True)
        )
        if claimed.rowcount != 1:
            raise CatalogError("These mappings changed. Reload them before saving.")
        db.query(CurriculumMapCell).filter_by(course_id=course_id).delete(
            synchronize_session=False
        )
        db.add_all(
            [
                CurriculumMapCell(
                    course_id=course_id,
                    objective_id=entry.objective_id,
                    level=entry.level,
                )
                for entry in data.entries
            ]
        )
        db.flush()
        db.refresh(course)
        after = course_mappings(db, course_id)
        audit(db, actor, "course_mappings", course_id, before, after)
        db.commit()
        return after
    except Exception:
        db.rollback()
        raise
