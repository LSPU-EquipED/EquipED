"""HTTP endpoints for the curriculum alignment check pipeline.

Separate, on-demand endpoints -- not part of the evaluation orchestrator's
automatic dispatch (design spec section 5).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.service import AuthenticatedUser

from .exceptions import (
    AlignmentCheckNotFoundError,
    CourseNotFoundError,
    DocumentAccessDeniedError,
    NoCurriculumMapError,
)
from .schemas import (
    AlignmentCheckResponse,
    CourseListResponse,
    CourseResponse,
    DocumentPageResponse,
    DocumentPagesResponse,
    RunAlignmentCheckRequest,
)
from .service import (
    get_alignment_check,
    get_document_pages_for_check,
    list_courses,
    run_curriculum_alignment_check,
)

router = APIRouter(prefix="/curriculum-map", tags=["curriculum-map"])


@router.get("/courses", response_model=CourseListResponse)
def list_courses_endpoint(
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> CourseListResponse:
    courses = list_courses(db)
    return CourseListResponse(
        items=[
            CourseResponse(
                course_id=c.course_id,
                course_code=c.course_code,
                course_title=c.course_title,
                program=c.program,
            )
            for c in courses
        ]
    )


@router.post(
    "/checks",
    response_model=AlignmentCheckResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_check_endpoint(
    body: RunAlignmentCheckRequest,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> AlignmentCheckResponse:
    try:
        check = run_curriculum_alignment_check(
            document_id=body.document_id,
            course_id=body.course_id,
            current_user_id=_current_user.id,
            db=db,
        )
    except DocumentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except CourseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except NoCurriculumMapError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _to_response(check, db)


@router.get("/checks/{check_id}", response_model=AlignmentCheckResponse)
def get_check_endpoint(
    check_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> AlignmentCheckResponse:
    try:
        check = get_alignment_check(check_id, _current_user.id, db)
    except (AlignmentCheckNotFoundError, DocumentAccessDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return _to_response(check, db)


@router.get("/checks/{check_id}/document-pages", response_model=DocumentPagesResponse)
def get_document_pages_endpoint(
    check_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> DocumentPagesResponse:
    try:
        pages = get_document_pages_for_check(check_id, _current_user.id, db)
    except (AlignmentCheckNotFoundError, DocumentAccessDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return DocumentPagesResponse(
        pages=[
            DocumentPageResponse(page_number=i, text=text)
            for i, text in enumerate(pages, start=1)
        ]
    )


def _to_response(check: Any, db: Any) -> AlignmentCheckResponse:
    from .models import Course

    course = db.get(Course, check.course_id)
    return AlignmentCheckResponse(
        check_id=check.check_id,
        document_id=check.document_id,
        course_id=check.course_id,
        course_title=course.course_title if course else "",
        run_at=check.run_at,
        model_name=check.model_name,
        objective_results=check.objective_results,
        summary=check.summary,
        success=check.success,
        error_message=check.error_message,
    )


__all__ = ["router"]
