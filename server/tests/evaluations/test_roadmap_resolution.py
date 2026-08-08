"""Orchestrator-side program-roadmap resolution tests.

Unit-tests the ``resolve_roadmap_course_context`` contract the orchestrator
relies on, then exercises ``run_evaluation_job``'s context construction
path with a stubbed Supervisor (no real LLM agents) to prove that a
resolved roadmap surfaces as a top-level ``"roadmap"`` key on the
supervisor context, and is absent when resolution fails.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.curriculum.models import (
    ProgramRoadmap,
    RoadmapCourse,
    RoadmapYear,
)
from server.modules.curriculum.service import resolve_roadmap_course_context
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import run_evaluation_job

from .conftest import _add_document, _seed_active_prompts


def _seed_roadmap(db_session) -> ProgramRoadmap:
    roadmap = ProgramRoadmap(
        program="BSInfoTech", specialization="IS", version_number=1, status="active"
    )
    db_session.add(roadmap)
    db_session.flush()
    year = RoadmapYear(roadmap_id=roadmap.roadmap_id, year_number=1, semester=1)
    db_session.add(year)
    db_session.flush()
    db_session.add(
        RoadmapCourse(
            roadmap_id=roadmap.roadmap_id,
            year_id=year.year_id,
            course_code="ITEC 105",
            course_title="Web Development",
            course_status="existing",
            tech_stack="Python",
            competency_stage="Intermediate",
        )
    )
    db_session.commit()
    return roadmap


def _sme_result(evaluation_id, document_id):
    from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore

    return AgentEvaluationResult(
        agent_name="sme",
        evaluation_id=evaluation_id,
        document_id=document_id,
        subtotal=3,
        criterion_scores=(
            CriterionScore(
                criterion_id="A-01",
                criterion_title="Criterion",
                score=3,
                justification="ok",
            ),
        ),
        summary="ok",
        model_name="local-model",
        processing_seconds=0.1,
        token_count=4,
        success=True,
        prompt_version_id=None,
    )


# ── Unit: resolve_roadmap_course_context ─────────────────────────────────


def test_resolve_returns_context_for_seeded_roadmap(db_session) -> None:
    _seed_roadmap(db_session)
    ctx = resolve_roadmap_course_context(
        program="BSInfoTech", course_code="ITEC 105", db=db_session
    )
    assert ctx is not None
    assert ctx["course_code"] == "ITEC 105"
    assert ctx["course_title"] == "Web Development"
    assert ctx["year"] == 1
    assert ctx["semester"] == 1
    assert ctx["tech_stack"] == "Python"
    assert ctx["competency_stage"] == "Intermediate"
    assert ctx["course_status"] == "existing"


def test_resolve_returns_none_for_proposed_course(db_session) -> None:
    roadmap = _seed_roadmap(db_session)
    year = (
        db_session.query(RoadmapYear)
        .filter_by(roadmap_id=roadmap.roadmap_id)
        .first()
    )
    db_session.add(
        RoadmapCourse(
            roadmap_id=roadmap.roadmap_id,
            year_id=year.year_id,
            course_code="ITEC 999",
            course_title="Proposed",
            course_status="proposed",
        )
    )
    db_session.commit()
    ctx = resolve_roadmap_course_context(
        program="BSInfoTech", course_code="ITEC 999", db=db_session
    )
    assert ctx is None


def test_resolve_returns_none_without_roadmap(db_session) -> None:
    ctx = resolve_roadmap_course_context(
        program="BSInfoTech", course_code="ITEC 105", db=db_session
    )
    assert ctx is None


# ── Orchestrator context building (stubbed Supervisor, no LLM) ───────────


def _run_orchestrator_capture(
    db_session,
    monkeypatch,
    *,
    course_code: str | None,
    seed_roadmap: bool,
) -> dict:
    from server.core import database as core_database
    from server.modules.agents.supervisor import SupervisorResult
    from server.modules.documents.models import Document
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email=f"owner-rm-{course_code or 'none'}@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    if course_code is not None:
        doc = db_session.get(Document, slm_id)
        doc.course_code = course_code
        db_session.commit()
    _seed_active_prompts(db_session)
    if seed_roadmap:
        _seed_roadmap(db_session)

    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=slm_id,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
        confirmed_program="BSInfoTech",
    )
    db_session.add(job)
    db_session.commit()

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    captured: dict = {}

    def fake_run_evaluation(
        self, *, evaluation_id, document_id, chunks, query_text=None, context=None
    ):
        captured.update(context or {})
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=[_sme_result(evaluation_id, document_id)],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor, "run_evaluation", fake_run_evaluation
    )

    run_evaluation_job(job.evaluation_id)
    return captured


def test_orchestrator_adds_roadmap_key_when_resolution_succeeds(
    db_session, monkeypatch
) -> None:
    captured = _run_orchestrator_capture(
        db_session, monkeypatch, course_code="ITEC 105", seed_roadmap=True
    )
    assert "roadmap" in captured
    roadmap = captured["roadmap"]
    assert roadmap["course_code"] == "ITEC 105"
    assert roadmap["course_title"] == "Web Development"
    assert roadmap["year"] == 1
    assert roadmap["semester"] == 1
    assert roadmap["tech_stack"] == "Python"
    assert roadmap["competency_stage"] == "Intermediate"
    assert roadmap["course_status"] == "existing"


def test_orchestrator_omits_roadmap_key_when_course_code_null(
    db_session, monkeypatch
) -> None:
    captured = _run_orchestrator_capture(
        db_session, monkeypatch, course_code=None, seed_roadmap=True
    )
    assert "roadmap" not in captured


def test_orchestrator_omits_roadmap_key_when_no_roadmap(
    db_session, monkeypatch
) -> None:
    captured = _run_orchestrator_capture(
        db_session, monkeypatch, course_code="ITEC 105", seed_roadmap=False
    )
    assert "roadmap" not in captured
