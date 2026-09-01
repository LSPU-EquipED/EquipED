"""Tests for supervisor orchestration and precomputed context."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from server.modules.admin.models import PromptVersion
from server.modules.agents.supervision.supervisor import Supervisor
from server.modules.documents.models import DocumentChunk
from server.tests.agents.helpers import (
    _BatchAgent,
    _FailingAgent,
    _make_dummy_snapshot,
    _seed_active_prompts,
)


def assert_path(path: Path) -> None:
    assert path == Path("/owned/uploads/source.pdf")


def test_supervisor_passes_all_chunks_and_loads_active_prompts(
    monkeypatch, db_session
) -> None:
    _seed_active_prompts(db_session)
    monkeypatch.setattr(
        db_session,
        "get",
        lambda model, _id: (
            type("Document", (), {"file_path": "source.pdf", "source_type": "slm"})()
            if model.__name__ == "Document"
            else None
        ),
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.resolve_document_pdf_path",
        lambda _path: Path("/owned/uploads/source.pdf"),
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.prepare_canonical_source",
        lambda path: (assert_path(path), "canonical source")[1],
    )
    prompt_row = db_session.query(PromptVersion).filter_by(agent_id="sme").one()
    agent = _BatchAgent()
    supervisor = Supervisor(agents=[agent], db=db_session)
    eval_id = uuid4()
    snapshots = (_make_dummy_snapshot("sme", evaluation_id=eval_id),)

    chunks = [
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="one",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        ),
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_type="slm",
            agent_domain="all",
            page_number=2,
            text="two",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        ),
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_type="slm",
            agent_domain="all",
            page_number=3,
            text="three",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        ),
    ]

    monkeypatch.setattr(
        "server.modules.agents.supervision.context.get_active_prompt",
        lambda agent_id, db: prompt_row,
    )

    result = supervisor.run_evaluation(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunks=chunks,
        form_snapshots=snapshots,
        context={
            "reference_document_ids": {
                "syllabus": uuid4(),
            }
        },
    )

    assert agent.batches == [["one", "two", "three"]]
    assert len(result.agent_results) == 1


def test_supervisor_continues_after_one_agent_failure(monkeypatch, db_session) -> None:
    _seed_active_prompts(db_session)
    monkeypatch.setattr(
        db_session,
        "get",
        lambda model, _id: (
            type("Document", (), {"file_path": "source.pdf", "source_type": "slm"})()
            if model.__name__ == "Document"
            else None
        ),
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.resolve_document_pdf_path",
        lambda _path: Path("/owned/uploads/source.pdf"),
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.context.prepare_canonical_source",
        lambda path: (assert_path(path), "canonical source")[1],
    )
    failing_agent = _FailingAgent()
    success_agent = _BatchAgent()
    supervisor = Supervisor(agents=[failing_agent, success_agent], db=db_session)

    prompt_rows = {
        agent_id: db_session.query(PromptVersion).filter_by(agent_id=agent_id).one()
        for agent_id in ["coordinator", "sme"]
    }

    monkeypatch.setattr(
        "server.modules.agents.supervision.context.get_active_prompt",
        lambda agent_id, db: prompt_rows[agent_id],
    )

    chunks = [
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="one",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        ),
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            source_type="slm",
            agent_domain="all",
            page_number=2,
            text="two",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        ),
    ]

    eval_id = uuid4()
    snapshots = (
        _make_dummy_snapshot("coordinator", evaluation_id=eval_id),
        _make_dummy_snapshot("sme", evaluation_id=eval_id),
    )

    result = supervisor.run_evaluation(
        evaluation_id=eval_id,
        document_id=uuid4(),
        chunks=chunks,
        form_snapshots=snapshots,
        context={
            "reference_document_ids": {
                "syllabus": uuid4(),
            }
        },
    )

    assert failing_agent.calls == 1
    assert success_agent.batches == [["one", "two"]]
    assert len(result.agent_results) == 2
    assert result.failures["coordinator"].startswith("RuntimeError (reference: ")


def test_precomputed_context_references() -> None:
    """ITSO execution _references extracts syllabus/curriculum context."""
    from server.modules.agents.itso import execution
    from server.modules.agents.runtime.context import ITSOExecutionContext

    precomputed = {
        "syllabus": ["syllabus-context-1", "syllabus-context-2"],
        "curriculum": ["curriculum-context"],
        "other": ["other-context"],
    }

    context = ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "page_number": 1, "text": "doc text"},),
        reference_document_ids={"syllabus": uuid4()},
        precomputed_context=precomputed,
    )
    assert execution._references(context) == [
        "syllabus-context-1",
        "syllabus-context-2",
        "curriculum-context",
    ]


def test_precomputed_context_references_empty_when_missing() -> None:
    """ITSO execution _references returns empty list when no syllabus or curriculum."""
    from server.modules.agents.itso import execution
    from server.modules.agents.runtime.context import ITSOExecutionContext

    context = ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "page_number": 1, "text": "doc text"},),
        reference_document_ids={},
        precomputed_context={},
    )
    assert execution._references(context) == []


def test_prepared_context_loads_authoritative_curriculum_text(
    db_session, monkeypatch
) -> None:
    """Full evaluation context builder loads curriculum chunk text in canonical order."""  # noqa: E501
    from server.modules.agents.supervision.context import EvaluationContextBuilder
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.models import Document

    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, source_type: True,
    )

    admin = create_user(
        db_session,
        name="Admin",
        email="admin-curr-text@lspu.edu.ph",
        password="password123",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    curr_doc = Document(
        document_id=uuid4(),
        title="Authoritative Curriculum",
        program="BSCS",
        source_type="curriculum",
        file_path="uploads/curr.pdf",
        uploaded_by=admin.user_id,
        processing_status="PROCESSED",
    )
    chunk1 = DocumentChunk(
        chunk_id=uuid4(),
        document_id=curr_doc.document_id,
        source_type="curriculum",
        agent_domain="all",
        page_number=1,
        chunk_index=0,
        text="Curriculum Section 1: Intro",
        token_count=5,
    )
    chunk2 = DocumentChunk(
        chunk_id=uuid4(),
        document_id=curr_doc.document_id,
        source_type="curriculum",
        agent_domain="all",
        page_number=2,
        chunk_index=1,
        text="Curriculum Section 2: Core",
        token_count=5,
    )
    db_session.add_all([curr_doc, chunk1, chunk2])
    db_session.commit()

    builder = EvaluationContextBuilder(db=db_session, agents=[])
    text = builder._load_authoritative_curriculum(
        {"curriculum": curr_doc.document_id}, program="BSCS"
    )
    assert text == "Curriculum Section 1: Intro\nCurriculum Section 2: Core"

    # Absent curriculum returns None
    text_none = builder._load_authoritative_curriculum({})
    assert text_none is None


def test_prepared_context_unready_curriculum_raises_supervisor_execution_error(
    db_session, monkeypatch
) -> None:
    """Unready curriculum (e.g. non-admin, missing chroma, not PROCESSED) raises SupervisorExecutionError."""  # noqa: E501
    import pytest
    from server.modules.agents.exceptions import SupervisorExecutionError
    from server.modules.agents.supervision.context import EvaluationContextBuilder
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user
    from server.modules.documents.models import Document

    faculty = create_user(
        db_session,
        name="Faculty",
        email="faculty-curr-unready@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    non_admin_curr = Document(
        document_id=uuid4(),
        title="Faculty Curriculum",
        program="BSCS",
        source_type="curriculum",
        file_path="uploads/curr2.pdf",
        uploaded_by=faculty.user_id,
        processing_status="PROCESSED",
    )
    chunk = DocumentChunk(
        chunk_id=uuid4(),
        document_id=non_admin_curr.document_id,
        source_type="curriculum",
        agent_domain="all",
        page_number=1,
        chunk_index=0,
        text="Curriculum Section 1",
        token_count=5,
    )
    db_session.add_all([non_admin_curr, chunk])
    db_session.commit()

    builder = EvaluationContextBuilder(db=db_session, agents=[])
    with pytest.raises(SupervisorExecutionError) as exc_info:
        builder._load_authoritative_curriculum(
            {"curriculum": non_admin_curr.document_id}, program="BSCS"
        )
    assert "not ready" in str(exc_info.value).lower()


def test_supervisor_agent_composition_full_vs_partial(db_session) -> None:
    """Default supervisor includes Coordinator for full; explicit partial agent list excludes Coordinator."""  # noqa: E501
    from server.modules.agents.gad.agent import GAD
    from server.modules.agents.itso.agent import ITSO
    from server.modules.agents.sme.agent import SME

    # Full intent (default agents)
    full_supervisor = Supervisor(db=db_session)
    full_agent_names = [a.agent_name for a in full_supervisor.agents]
    assert "coordinator" in full_agent_names
    assert set(full_agent_names) == {"sme", "coordinator", "gad", "itso"}

    # Partial intent
    partial_supervisor = Supervisor(agents=[SME(), GAD(), ITSO()], db=db_session)
    partial_agent_names = [a.agent_name for a in partial_supervisor.agents]
    assert "coordinator" not in partial_agent_names
    assert set(partial_agent_names) == {"sme", "gad", "itso"}


def test_context_builder_rejects_legacy_fixed_criterion_prompts(db_session) -> None:
    """EvaluationContextBuilder rejects active prompt text with legacy identifiers."""
    import pytest
    from server.modules.agents.exceptions import SupervisorExecutionError
    from server.modules.agents.gad.agent import GAD
    from server.modules.agents.itso.agent import ITSO
    from server.modules.agents.supervision.context import EvaluationContextBuilder

    # Seed GAD with legacy GAD-01 identifier
    gad_legacy = PromptVersion(
        agent_id="gad",
        version_number=1,
        prompt_text="Extract facts for GAD-01 and GAD-02 criteria.",
        is_active=True,
    )
    db_session.add(gad_legacy)
    db_session.commit()

    builder_gad = EvaluationContextBuilder(db=db_session, agents=[GAD()])
    with pytest.raises(SupervisorExecutionError) as exc_info:
        builder_gad._load_active_prompt_versions()
    assert "legacy fixed criterion identifiers" in str(exc_info.value)
    assert "gad" in str(exc_info.value)

    # Deactivate legacy GAD and set generic GAD
    gad_legacy.is_active = False
    gad_generic = PromptVersion(
        agent_id="gad",
        version_number=2,
        prompt_text="Generic GAD role prompt with runtime criteria only.",
        is_active=True,
    )
    # Seed ITSO with legacy ITSO-01 identifier
    itso_legacy = PromptVersion(
        agent_id="itso",
        version_number=1,
        prompt_text="Evaluate ITSO-01 (IP) and ITSO-02 (References).",
        is_active=True,
    )
    db_session.add_all([gad_generic, itso_legacy])
    db_session.commit()

    builder_itso = EvaluationContextBuilder(db=db_session, agents=[ITSO()])
    with pytest.raises(SupervisorExecutionError) as exc_info:
        builder_itso._load_active_prompt_versions()
    assert "legacy fixed criterion identifiers" in str(exc_info.value)
    assert "itso" in str(exc_info.value)

    # Deactivate legacy ITSO and set generic ITSO
    itso_legacy.is_active = False
    itso_generic = PromptVersion(
        agent_id="itso",
        version_number=2,
        prompt_text="Generic ITSO role prompt with runtime criteria only.",
        is_active=True,
    )
    db_session.add(itso_generic)
    db_session.commit()

    # Now both GAD and ITSO generic prompts are accepted
    builder_both = EvaluationContextBuilder(db=db_session, agents=[GAD(), ITSO()])
    prompts = builder_both._load_active_prompt_versions()
    assert "gad" in prompts
    assert "itso" in prompts
    assert (
        prompts["gad"].prompt_text
        == "Generic GAD role prompt with runtime criteria only."
    )
    assert (
        prompts["itso"].prompt_text
        == "Generic ITSO role prompt with runtime criteria only."
    )
    assert prompts["gad"].version_id == gad_generic.version_id
    assert prompts["itso"].version_id == itso_generic.version_id
