"""Model, service, and endpoint tests for the program-roadmap feature.

Covers the three roadmap tables' natural-key/status constraints, the
seed-style upsert flow (``list_roadmaps`` / ``get_roadmap_detail``), the
``resolve_roadmap_course_context`` contract used by the evaluation
orchestrator, the ``list_roadmap_courses`` filters, and the authenticated
``/curriculum-map/roadmaps*`` endpoints.
"""

from __future__ import annotations

import uuid

import pytest
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.curriculum import service
from server.modules.curriculum.exceptions import RoadmapNotFoundError
from server.modules.curriculum.models import (
    ProgramRoadmap,
    RoadmapCourse,
    RoadmapYear,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def _make_roadmap(
    db_session,
    *,
    program: str = "BSInfoTech",
    specialization: str | None = "Intelligent Systems",
    version_number: int = 1,
    status: str = "active",
    source_document_path: str | None = None,
) -> ProgramRoadmap:
    roadmap = ProgramRoadmap(
        program=program,
        specialization=specialization,
        version_number=version_number,
        status=status,
        source_document_path=source_document_path,
    )
    db_session.add(roadmap)
    db_session.flush()
    return roadmap


def _make_year(
    db_session,
    roadmap: ProgramRoadmap,
    *,
    year_number: int = 1,
    semester: int | None = None,
    label: str | None = None,
    description: str | None = None,
) -> RoadmapYear:
    year = RoadmapYear(
        roadmap_id=roadmap.roadmap_id,
        year_number=year_number,
        semester=semester,
        label=label,
        description=description,
    )
    db_session.add(year)
    db_session.flush()
    return year


def _make_course(
    db_session,
    roadmap: ProgramRoadmap,
    year: RoadmapYear,
    *,
    course_code: str = "ITEC 105",
    course_title: str = "Web Development",
    course_status: str = "existing",
    tech_stack: str | None = None,
    competency_stage: str | None = None,
) -> RoadmapCourse:
    course = RoadmapCourse(
        roadmap_id=roadmap.roadmap_id,
        year_id=year.year_id,
        course_code=course_code,
        course_title=course_title,
        course_status=course_status,
        tech_stack=tech_stack,
        competency_stage=competency_stage,
    )
    db_session.add(course)
    db_session.flush()
    return course


# ── Model constraints ─────────────────────────────────────────────────────


def test_natural_key_uniqueness_is_enforced(db_session) -> None:
    _make_roadmap(
        db_session, program="BSInfoTech", specialization="IS", version_number=1
    )
    duplicate = ProgramRoadmap(
        program="BSInfoTech", specialization="IS", version_number=1
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_roadmap_status_check_constraint_rejects_invalid(db_session) -> None:
    roadmap = ProgramRoadmap(
        program="BSInfoTech", specialization="IS", version_number=1, status="bogus"
    )
    db_session.add(roadmap)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_roadmap_accepts_active_and_retired_statuses(db_session) -> None:
    active = ProgramRoadmap(
        program="BSInfoTech", specialization="IS", version_number=1, status="active"
    )
    retired = ProgramRoadmap(
        program="BSCS", specialization="IS", version_number=2, status="retired"
    )
    db_session.add_all([active, retired])
    db_session.commit()
    assert active.status == "active"
    assert retired.status == "retired"


def test_roadmap_course_status_check_constraint_rejects_invalid(db_session) -> None:
    roadmap = _make_roadmap(db_session)
    year = _make_year(db_session, roadmap)
    course = RoadmapCourse(
        roadmap_id=roadmap.roadmap_id,
        year_id=year.year_id,
        course_code="ITEC 105",
        course_title="Web Development",
        course_status="bogus",
    )
    db_session.add(course)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_roadmap_course_accepts_existing_and_proposed(db_session) -> None:
    roadmap = _make_roadmap(db_session)
    year = _make_year(db_session, roadmap)
    existing = _make_course(db_session, roadmap, year, course_status="existing")
    proposed = RoadmapCourse(
        roadmap_id=roadmap.roadmap_id,
        year_id=year.year_id,
        course_code="ITEC 999",
        course_title="Proposed Course",
        course_status="proposed",
    )
    db_session.add(proposed)
    db_session.commit()
    assert existing.course_status == "existing"
    assert proposed.course_status == "proposed"


# ── Service: list / detail ───────────────────────────────────────────────


def test_list_roadmaps_orders_by_program_then_version_desc(db_session) -> None:
    r1 = _make_roadmap(
        db_session, program="BSInfoTech", specialization="IS", version_number=1
    )
    r2 = _make_roadmap(
        db_session, program="BSInfoTech", specialization="IS", version_number=2
    )
    db_session.commit()

    roadmaps = service.list_roadmaps(db_session)
    assert [r.roadmap_id for r in roadmaps] == [r2.roadmap_id, r1.roadmap_id]


def test_get_roadmap_detail_orders_years_and_attaches_courses(db_session) -> None:
    roadmap = _make_roadmap(db_session, version_number=1)
    y1 = _make_year(db_session, roadmap, year_number=1, semester=1, label="First Year")
    _y2 = _make_year(
        db_session, roadmap, year_number=2, semester=None, label="Second Year"
    )
    _make_course(
        db_session, roadmap, y1, course_code="ITEC 105", course_title="Web Development"
    )
    db_session.commit()

    fetched, years = service.get_roadmap_detail(roadmap.roadmap_id, db_session)
    assert fetched.roadmap_id == roadmap.roadmap_id
    assert [yr["year_number"] for yr in years] == [1, 2]
    assert [yr["semester"] for yr in years] == [1, None]
    assert years[0]["courses"][0].course_code == "ITEC 105"
    assert years[1]["courses"] == []


def test_get_roadmap_raises_for_missing(db_session) -> None:
    with pytest.raises(RoadmapNotFoundError):
        service.get_roadmap(uuid.uuid4(), db_session)


# ── Service: resolve_roadmap_course_context ──────────────────────────────


def test_resolve_existing_course_returns_full_dict(db_session) -> None:
    roadmap = _make_roadmap(db_session)
    year = _make_year(db_session, roadmap, year_number=1, semester=1)
    _make_course(
        db_session,
        roadmap,
        year,
        course_code="ITEC 105",
        course_title="Web Development",
        tech_stack="Python, Django",
        competency_stage="Intermediate",
    )
    db_session.commit()

    ctx = service.resolve_roadmap_course_context(
        program="BSInfoTech", course_code="ITEC 105", db=db_session
    )
    assert ctx == {
        "course_code": "ITEC 105",
        "course_title": "Web Development",
        "year": 1,
        "semester": 1,
        "tech_stack": "Python, Django",
        "competency_stage": "Intermediate",
        "course_status": "existing",
    }


def test_resolve_returns_none_for_null_program(db_session) -> None:
    roadmap = _make_roadmap(db_session)
    year = _make_year(db_session, roadmap)
    _make_course(db_session, roadmap, year, course_code="ITEC 105")
    db_session.commit()
    assert (
        service.resolve_roadmap_course_context(
            program=None, course_code="ITEC 105", db=db_session
        )
        is None
    )


def test_resolve_returns_none_for_null_course_code(db_session) -> None:
    roadmap = _make_roadmap(db_session)
    year = _make_year(db_session, roadmap)
    _make_course(db_session, roadmap, year, course_code="ITEC 105")
    db_session.commit()
    assert (
        service.resolve_roadmap_course_context(
            program="BSInfoTech", course_code=None, db=db_session
        )
        is None
    )


def test_resolve_returns_none_when_only_retired_roadmap(db_session) -> None:
    roadmap = _make_roadmap(db_session, status="retired")
    year = _make_year(db_session, roadmap)
    _make_course(db_session, roadmap, year, course_code="ITEC 105")
    db_session.commit()
    assert (
        service.resolve_roadmap_course_context(
            program="BSInfoTech", course_code="ITEC 105", db=db_session
        )
        is None
    )


def test_resolve_returns_none_for_proposed_course(db_session) -> None:
    roadmap = _make_roadmap(db_session)
    year = _make_year(db_session, roadmap)
    _make_course(
        db_session,
        roadmap,
        year,
        course_code="ITEC 999",
        course_status="proposed",
    )
    db_session.commit()
    assert (
        service.resolve_roadmap_course_context(
            program="BSInfoTech", course_code="ITEC 999", db=db_session
        )
        is None
    )


def test_resolve_matches_case_insensitively(db_session) -> None:
    roadmap = _make_roadmap(db_session)
    year = _make_year(db_session, roadmap)
    _make_course(db_session, roadmap, year, course_code="ITEC 105")
    db_session.commit()

    ctx = service.resolve_roadmap_course_context(
        program="BSInfoTech", course_code="itec 105", db=db_session
    )
    assert ctx is not None
    assert ctx["course_code"] == "ITEC 105"


def test_resolve_bsit_alias_resolves_against_bsinfotech(db_session) -> None:
    roadmap = _make_roadmap(db_session, program="BSInfoTech")
    year = _make_year(db_session, roadmap)
    _make_course(db_session, roadmap, year, course_code="ITEC 105")
    db_session.commit()

    ctx = service.resolve_roadmap_course_context(
        program="BSIT", course_code="ITEC 105", db=db_session
    )
    assert ctx is not None
    assert ctx["course_code"] == "ITEC 105"


def test_resolve_picks_highest_version_when_multiple_active(db_session) -> None:
    v1 = _make_roadmap(db_session, version_number=1)
    y1 = _make_year(db_session, v1)
    _make_course(db_session, v1, y1, course_code="ITEC 105", course_title="Version One")

    v2 = _make_roadmap(db_session, version_number=2)
    y2 = _make_year(db_session, v2)
    _make_course(db_session, v2, y2, course_code="ITEC 105", course_title="Version Two")
    db_session.commit()

    ctx = service.resolve_roadmap_course_context(
        program="BSInfoTech", course_code="ITEC 105", db=db_session
    )
    assert ctx is not None
    assert ctx["course_title"] == "Version Two"


def test_resolve_returns_none_when_no_roadmap_exists(db_session) -> None:
    assert (
        service.resolve_roadmap_course_context(
            program="BSInfoTech", course_code="ITEC 105", db=db_session
        )
        is None
    )


def test_resolve_with_duplicate_course_code_returns_first_deterministically(
    db_session,
) -> None:
    """A legacy DB carrying duplicate (roadmap_id, course_code) rows must not
    make resolution crash; the lowest ``course_id`` wins deterministically.

    The model now declares a unique constraint, so a legacy-duplicate shape is
    simulated by recreating ``roadmap_courses`` without that constraint (as a
    pre-migration DB would have it) and inserting two rows sharing a code.
    """
    roadmap = _make_roadmap(db_session)
    year = _make_year(db_session, roadmap)
    db_session.commit()

    # Rebuild roadmap_courses without the (roadmap_id, course_code) unique
    # constraint, mimicking the schema before 20260808_0002.
    db_session.execute(text("DROP TABLE roadmap_courses"))
    db_session.execute(
        text(
            "CREATE TABLE roadmap_courses ("
            "  id CHAR(32) PRIMARY KEY,"
            "  roadmap_id CHAR(32) NOT NULL,"
            "  year_id CHAR(32) NOT NULL,"
            "  course_code VARCHAR(50) NOT NULL,"
            "  course_title VARCHAR(300) NOT NULL,"
            "  course_id CHAR(32),"
            "  course_status VARCHAR(20) NOT NULL,"
            "  tech_stack TEXT,"
            "  competency_stage VARCHAR(100),"
            "  learning_outcomes_summary TEXT,"
            "  portfolio_project_suggestion TEXT,"
            "  relevant_certification VARCHAR(300)"
            ")"
        )
    )
    first = _make_course(
        db_session,
        roadmap,
        year,
        course_code="ITEC 105",
        course_title="Duplicate One",
    )
    second = _make_course(
        db_session,
        roadmap,
        year,
        course_code="ITEC 105",
        course_title="Duplicate Two",
    )
    db_session.commit()

    ctx = service.resolve_roadmap_course_context(
        program="BSInfoTech", course_code="ITEC 105", db=db_session
    )
    assert ctx is not None
    # Deterministic pick: lowest course_id wins.
    expected = first if first.id < second.id else second
    assert ctx["course_title"] == expected.course_title


def test_resolve_matches_program_case_insensitively_lowercase_seed(db_session) -> None:
    """A roadmap seeded with a lowercase program resolves for a confirmed
    program in canonical case."""
    roadmap = _make_roadmap(db_session, program="bscs")
    year = _make_year(db_session, roadmap)
    _make_course(db_session, roadmap, year, course_code="ITEC 105")
    db_session.commit()

    ctx = service.resolve_roadmap_course_context(
        program="BSCS", course_code="ITEC 105", db=db_session
    )
    assert ctx is not None
    assert ctx["course_code"] == "ITEC 105"


def test_resolve_matches_program_case_insensitively_uppercase_seed(db_session) -> None:
    """A roadmap seeded in canonical case resolves for a confirmed program in
    lowercase."""
    roadmap = _make_roadmap(db_session, program="BSCS")
    year = _make_year(db_session, roadmap)
    _make_course(db_session, roadmap, year, course_code="ITEC 105")
    db_session.commit()

    ctx = service.resolve_roadmap_course_context(
        program="bscs", course_code="ITEC 105", db=db_session
    )
    assert ctx is not None
    assert ctx["course_code"] == "ITEC 105"


# ── Service: list_roadmap_courses ────────────────────────────────────────


def test_list_roadmap_courses_filters_by_year(db_session) -> None:
    roadmap = _make_roadmap(db_session)
    y1 = _make_year(db_session, roadmap, year_number=1)
    y2 = _make_year(db_session, roadmap, year_number=2)
    _make_course(db_session, roadmap, y1, course_code="A101")
    _make_course(db_session, roadmap, y2, course_code="B202")
    db_session.commit()

    courses = service.list_roadmap_courses(roadmap.roadmap_id, 1, None, db_session)
    assert [c.course_code for c in courses] == ["A101"]


def test_list_roadmap_courses_filters_by_semester(db_session) -> None:
    roadmap = _make_roadmap(db_session)
    y1s1 = _make_year(db_session, roadmap, year_number=1, semester=1)
    y1s2 = _make_year(db_session, roadmap, year_number=1, semester=2)
    _make_course(db_session, roadmap, y1s1, course_code="S1A")
    _make_course(db_session, roadmap, y1s2, course_code="S2A")
    db_session.commit()

    sem1 = service.list_roadmap_courses(roadmap.roadmap_id, 1, 1, db_session)
    assert [c.course_code for c in sem1] == ["S1A"]


def test_list_roadmap_courses_none_semester_returns_all(db_session) -> None:
    roadmap = _make_roadmap(db_session)
    y1s1 = _make_year(db_session, roadmap, year_number=1, semester=1)
    y1s2 = _make_year(db_session, roadmap, year_number=1, semester=2)
    _make_course(db_session, roadmap, y1s1, course_code="S1A")
    _make_course(db_session, roadmap, y1s2, course_code="S2A")
    db_session.commit()

    courses = service.list_roadmap_courses(roadmap.roadmap_id, 1, None, db_session)
    assert [c.course_code for c in courses] == ["S1A", "S2A"]


def test_list_roadmap_courses_raises_for_missing_roadmap(db_session) -> None:
    with pytest.raises(RoadmapNotFoundError):
        service.list_roadmap_courses(uuid.uuid4(), 1, None, db_session)


# ── Endpoints ────────────────────────────────────────────────────────────


def _login(client, db_session, email="faculty-roadmap@lspu.edu.ph"):
    user = create_user(
        db_session,
        name="Faculty User",
        email=email,
        password="correct-horse-battery",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "correct-horse-battery"}
    )
    assert response.status_code == 200
    return user


def test_roadmaps_list_requires_auth(client) -> None:
    response = client.get("/api/v1/curriculum-map/roadmaps")
    assert response.status_code == 401


def test_roadmaps_list_returns_seeded_roadmaps(client, db_session) -> None:
    _login(client, db_session)
    _make_roadmap(
        db_session, program="BSInfoTech", specialization="IS", version_number=1
    )
    db_session.commit()

    response = client.get("/api/v1/curriculum-map/roadmaps")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["program"] == "BSInfoTech"
    assert body["items"][0]["version_number"] == 1
    # source_document_path is intentionally omitted from summary responses.
    assert "source_document_path" not in body["items"][0]


def test_roadmap_detail_returns_404_for_unknown_id(client, db_session) -> None:
    _login(client, db_session)
    response = client.get(f"/api/v1/curriculum-map/roadmaps/{uuid.uuid4()}")
    assert response.status_code == 404


def test_roadmap_detail_returns_years_with_courses(client, db_session) -> None:
    _login(client, db_session)
    roadmap = _make_roadmap(db_session)
    year = _make_year(
        db_session, roadmap, year_number=1, semester=1, label="First Year"
    )
    _make_course(
        db_session,
        roadmap,
        year,
        course_code="ITEC 105",
        course_title="Web Development",
        tech_stack="Python",
    )
    db_session.commit()

    response = client.get(f"/api/v1/curriculum-map/roadmaps/{roadmap.roadmap_id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["years"]) == 1
    assert body["years"][0]["year_number"] == 1
    assert body["years"][0]["courses"][0]["course_code"] == "ITEC 105"
    assert body["years"][0]["courses"][0]["tech_stack"] == "Python"


def test_roadmap_courses_filters_by_year(client, db_session) -> None:
    _login(client, db_session)
    roadmap = _make_roadmap(db_session)
    y1 = _make_year(db_session, roadmap, year_number=1)
    y2 = _make_year(db_session, roadmap, year_number=2)
    _make_course(db_session, roadmap, y1, course_code="A101")
    _make_course(db_session, roadmap, y2, course_code="B202")
    db_session.commit()

    response = client.get(
        f"/api/v1/curriculum-map/roadmaps/{roadmap.roadmap_id}/courses?year=1"
    )
    assert response.status_code == 200
    assert [c["course_code"] for c in response.json()] == ["A101"]


def test_roadmap_courses_returns_404_for_unknown_roadmap(client, db_session) -> None:
    _login(client, db_session)
    response = client.get(
        f"/api/v1/curriculum-map/roadmaps/{uuid.uuid4()}/courses?year=1"
    )
    assert response.status_code == 404
