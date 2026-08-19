"""Coordinator program-roadmap enrichment tests.

Locks in the advisory roadmap note formatting (``_format_roadmap_note``),
the byte-identical-by-default behavior of ``extract_basket_a1`` when
``roadmap_context`` is None, that ``Coordinator.run`` accepts the new
``roadmap_context`` kwarg without error, and that the
``partial_without_curriculum`` orchestrator path still excludes Coordinator.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from server.modules.agents.coordinator.agent import Coordinator
from server.modules.agents.coordinator.curriculum import (
    format_roadmap_note as _format_roadmap_note,
)
from server.modules.agents.sme.oracle import extraction, registry
from server.tests.agents.helpers import _BASKET_A1, SequencedFakeClient

_TITLES = {code: f"{code} Coordinator Title" for code in registry.REGISTERED_CODES}

_CHUNK_INFOS = [{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}]

_ROADMAP_CTX = {
    "course_code": "ITEC 105",
    "course_title": "Web Development",
    "year": 2,
    "semester": 1,
    "tech_stack": "Python",
    "competency_stage": "Intermediate",
    "course_status": "existing",
}


def _make_agent(monkeypatch, client) -> Coordinator:
    agent = Coordinator(llm_client=client)
    monkeypatch.setattr(
        Coordinator, "_load_document_text", lambda self, document_id: None
    )
    monkeypatch.setattr(
        "server.modules.agents.sme.pipeline.get_active_rubric_criteria",
        lambda agent_id, db=None: _TITLES,
    )
    return agent


# ── _format_roadmap_note ─────────────────────────────────────────────────


def test_format_note_full_dict_contains_all_fields() -> None:
    note = _format_roadmap_note(_ROADMAP_CTX)
    assert "Year 2" in note
    assert "Semester 1" in note
    assert "Intermediate" in note
    assert "Python" in note


def test_format_note_omits_missing_semester() -> None:
    ctx = dict(_ROADMAP_CTX, semester=None)
    note = _format_roadmap_note(ctx)
    assert "Semester" not in note
    assert "Year 2" in note


def test_format_note_empty_and_none_are_empty_strings() -> None:
    assert _format_roadmap_note({}) == ""
    assert _format_roadmap_note(None) == ""


def test_format_note_non_dict_returns_empty_string() -> None:
    assert _format_roadmap_note("not a dict") == ""
    assert _format_roadmap_note(42) == ""


# ── extract_basket_a1 additive roadmap_context ───────────────────────────


class _CaptureClient:
    """Records the prompt(s) sent to the LLM and returns a minimal basket."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, **_: object) -> str:
        self.prompts.append(prompt)
        return json.dumps({"objectives": []})


def test_extract_basket_a1_none_identical_to_not_passing() -> None:
    c1 = _CaptureClient()
    c2 = _CaptureClient()
    extraction.extract_basket_a1(c1, "some slm text")
    extraction.extract_basket_a1(c2, "some slm text", roadmap_context=None)
    assert c1.prompts == c2.prompts
    assert "PROGRAM ROADMAP CONTEXT" not in c1.prompts[0]


def test_extract_basket_a1_appends_roadmap_context() -> None:
    client = _CaptureClient()
    extraction.extract_basket_a1(
        client, "some slm text", roadmap_context="Year 2 with Python competency"
    )
    prompt = client.prompts[0]
    assert "PROGRAM ROADMAP CONTEXT" in prompt
    assert "Year 2 with Python competency" in prompt


# ── Coordinator.run with roadmap_context ─────────────────────────────────


def test_coordinator_run_accepts_roadmap_context(monkeypatch) -> None:
    client = SequencedFakeClient([_BASKET_A1])
    agent = _make_agent(monkeypatch, client)

    result = agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="full slm text",
        roadmap_context=_ROADMAP_CTX,
    )

    assert client.calls == 1
    assert result.success is True
    assert [s.criterion_id for s in result.criterion_scores] == ["A-05"]


# ── Partial flow: Coordinator excluded without curriculum ────────────────


def test_partial_without_curriculum_excludes_coordinator(
    db_session, monkeypatch
) -> None:
    from server.core import database as core_database
    from server.modules.agents.contracts import AgentEvaluationResult
    from server.modules.agents.supervision.result import SupervisorResult
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.evaluations import orchestrator as evaluation_orchestrator
    from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
    from server.tests.agents.helpers import _seed_active_prompts
    from sqlalchemy.orm import sessionmaker

    owner = create_user(
        db_session,
        name="Owner",
        email="owner-partial-rm@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    slm_id = uuid.uuid4()
    db_session.add(
        Document(
            document_id=slm_id,
            title="slm doc",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{slm_id}.pdf",
            uploaded_by=owner.user_id,
            uploaded_at=datetime.now(UTC),
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db_session.add(
        DocumentChunk(
            chunk_id=uuid.uuid4(),
            document_id=slm_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="chunk for slm",
            token_count=4,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    db_session.commit()
    _seed_active_prompts(db_session)

    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=slm_id,
        syllabus_id=None,
        curriculum_id=None,
        status=EvaluationStatus.SUBMITTED.value,
        error_message=None,
        submitted_by=owner.user_id,
        submitted_at=datetime.now(UTC),
        completed_at=None,
        partial_without_curriculum=True,
        partial_reason=(
            "No curriculum reference was available; "
            "Coordinator review was skipped."
        ),
    )
    db_session.add(job)
    db_session.commit()

    session_factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, autocommit=False
    )
    monkeypatch.setattr(core_database, "get_session_factory", lambda: session_factory)

    captured_agents: list[str] = []

    def fake_run_evaluation(
        self, *, evaluation_id, document_id, chunks, query_text=None, context=None
    ):
        captured_agents[:] = [
            getattr(a, "agent_name", type(a).__name__) for a in self.agents
        ]
        return SupervisorResult(
            evaluation_id=evaluation_id,
            document_id=document_id,
            agent_results=[
                AgentEvaluationResult(
                    agent_name="sme",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=3,
                    criterion_scores=(),
                    summary="ok",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    success=True,
                    prompt_version_id=None,
                ),
                AgentEvaluationResult(
                    agent_name="gad",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=3,
                    criterion_scores=(),
                    summary="ok",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    success=True,
                    prompt_version_id=None,
                ),
                AgentEvaluationResult(
                    agent_name="itso",
                    evaluation_id=evaluation_id,
                    document_id=document_id,
                    subtotal=3,
                    criterion_scores=(),
                    summary="ok",
                    model_name="local-model",
                    processing_seconds=0.1,
                    token_count=4,
                    success=True,
                    prompt_version_id=None,
                ),
            ],
        )

    monkeypatch.setattr(
        evaluation_orchestrator.Supervisor, "run_evaluation", fake_run_evaluation
    )

    evaluation_orchestrator.run_evaluation_job(job.evaluation_id)

    assert "coordinator" not in captured_agents
    assert len(captured_agents) == 3
