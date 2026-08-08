"""HTTP endpoints for the curriculum alignment check pipeline.

Separate, on-demand endpoints -- not part of the evaluation orchestrator's
automatic dispatch (design spec section 5).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.service import AuthenticatedUser

from .exceptions import (
    RoadmapNotFoundError,
)
from .schemas import (
    CourseListResponse,
    CourseResponse,
    RoadmapCourseResponse,
    RoadmapDetailResponse,
    RoadmapListResponse,
    RoadmapSummaryResponse,
    RoadmapYearResponse,
)
from .service import (
    get_roadmap_detail,
    list_courses,
    list_roadmap_courses,
    list_roadmaps,
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


@router.get("/roadmaps", response_model=RoadmapListResponse)
def list_roadmaps_endpoint(
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> RoadmapListResponse:
    roadmaps = list_roadmaps(db)
    return RoadmapListResponse(
        items=[
            RoadmapSummaryResponse(
                roadmap_id=r.roadmap_id,
                program=r.program,
                specialization=r.specialization,
                version_number=r.version_number,
                status=r.status,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in roadmaps
        ],
        total=len(roadmaps),
    )


@router.get("/roadmaps/{roadmap_id}", response_model=RoadmapDetailResponse)
def get_roadmap_endpoint(
    roadmap_id: UUID,
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> RoadmapDetailResponse:
    try:
        roadmap, years = get_roadmap_detail(roadmap_id, db)
    except RoadmapNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return RoadmapDetailResponse(
        roadmap_id=roadmap.roadmap_id,
        program=roadmap.program,
        specialization=roadmap.specialization,
        version_number=roadmap.version_number,
        status=roadmap.status,
        years=[
            RoadmapYearResponse(
                year_id=y["year_id"],
                year_number=y["year_number"],
                semester=y["semester"],
                label=y["label"],
                description=y["description"],
                courses=[
                    RoadmapCourseResponse(
                        id=c.id,
                        course_code=c.course_code,
                        course_title=c.course_title,
                        course_status=c.course_status,
                        tech_stack=c.tech_stack,
                        competency_stage=c.competency_stage,
                        learning_outcomes_summary=c.learning_outcomes_summary,
                    )
                    for c in y["courses"]
                ],
            )
            for y in years
        ],
    )


@router.get(
    "/roadmaps/{roadmap_id}/courses",
    response_model=list[RoadmapCourseResponse],
)
def list_roadmap_courses_endpoint(
    roadmap_id: UUID,
    year: int = Query(..., ge=1, le=10),
    semester: int | None = Query(default=None, ge=1, le=2),
    _current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: Any = Depends(get_db_session),
) -> list[RoadmapCourseResponse]:
    try:
        courses = list_roadmap_courses(roadmap_id, year, semester, db)
    except RoadmapNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return [
        RoadmapCourseResponse(
            id=c.id,
            course_code=c.course_code,
            course_title=c.course_title,
            course_status=c.course_status,
            tech_stack=c.tech_stack,
            competency_stage=c.competency_stage,
            learning_outcomes_summary=c.learning_outcomes_summary,
        )
        for c in courses
    ]




__all__ = ["router"]
