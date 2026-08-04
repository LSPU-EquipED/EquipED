"""HTTP endpoints for the curriculum alignment check pipeline.

Separate, on-demand endpoints -- not part of the evaluation orchestrator's
automatic dispatch (design spec section 5).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from server.core.config import Settings, get_settings
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.service import AuthenticatedUser

from .exceptions import (
    AlignmentCheckCooldownError,
    AlignmentCheckNotFoundError,
    AlignmentCheckRateLimitError,
    CourseNotFoundError,
    CourseProgramMismatchError,
    CurriculumMapProgramError,
    DocumentAccessDeniedError,
    DocumentNotReadyError,
    DocumentProgramError,
    DocumentSourceTypeError,
    NoCurriculumMapError,
    NoUsableDocumentTextError,
)
from .limiter import alignment_check_slot_context
from .schemas import (
    AlignmentCheckListItemResponse,
    AlignmentCheckListResponse,
    AlignmentCheckResponse,
    CourseListResponse,
    CourseResponse,
    DocumentPageResponse,
    DocumentPagesResponse,
    RunAlignmentCheckRequest,
)
from .service import (
    _require_owned_document,
    delete_alignment_check,
    get_alignment_check,
    get_document_pages_for_check,
    list_alignment_checks,
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


@router.get("/checks", response_model=AlignmentCheckListResponse)
def list_checks_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> AlignmentCheckListResponse:
    items, total = list_alignment_checks(
        current_user_id=_current_user.id, page=page, page_size=page_size, db=db
    )
    return AlignmentCheckListResponse(
        items=[AlignmentCheckListItemResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
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
    settings: Settings = Depends(get_settings),
) -> AlignmentCheckResponse:
    try:
        # Keep ownership/program-scoping behavior unchanged: deny invalid document
        # access before any rate-limit scheduling.
        _require_owned_document(body.document_id, _current_user.id, db)

        with alignment_check_slot_context(
            user_id=_current_user.id,
            max_global=settings.curriculum_alignment_max_concurrent_checks,
            max_per_user=settings.curriculum_alignment_max_checks_per_user,
        ):
            check = run_curriculum_alignment_check(
                document_id=body.document_id,
                course_id=body.course_id,
                current_user_id=_current_user.id,
                db=db,
            )
    except AlignmentCheckRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except AlignmentCheckCooldownError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except DocumentAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except CourseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except (
        DocumentSourceTypeError,
        DocumentProgramError,
        CourseProgramMismatchError,
        CurriculumMapProgramError,
        NoCurriculumMapError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except (DocumentNotReadyError, NoUsableDocumentTextError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
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


@router.delete("/checks/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_check_endpoint(
    check_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> None:
    try:
        delete_alignment_check(check_id, _current_user.id, db)
    except (AlignmentCheckNotFoundError, DocumentAccessDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


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
            DocumentPageResponse(page_number=page.page_number, text=page.text)
            for page in pages
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
