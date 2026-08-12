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
    _RetrievedChunk,
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
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
        context={
            "reference_document_ids": {
                "syllabus": uuid4(),
                "curriculum": uuid4(),
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

    result = supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
        context={
            "reference_document_ids": {
                "syllabus": uuid4(),
                "curriculum": uuid4(),
            }
        },
    )

    assert failing_agent.calls == 1
    assert success_agent.batches == [["one", "two"]]
    assert len(result.agent_results) == 2
    assert result.failures["coordinator"].startswith("RuntimeError (reference: ")


def test_precomputed_context_respects_per_agent_rubric_scope(monkeypatch) -> None:
    """Each agent should only receive its own rubric context from precomputed dict."""
    from server.modules.agents.itso import execution
    from server.modules.agents.runtime.context import ITSOExecutionContext

    monkeypatch.setattr(
        "server.modules.agents.itso.execution.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.itso.execution.resolve_collection_name",
        lambda source_type: source_type,
    )

    # Precomputed dict has entries for all source types, but each agent
    # should only use its own rubric_source_type.
    precomputed = {
        "rubric_sme": ["sme-only-context"],
        "rubric_coord": ["coord-only-context"],
        "rubric_gad": ["gad-only-context"],
        "rubric_itso": ["itso-only-context"],
        "syllabus": ["syllabus-context"],
    }

    context = ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "page_number": 1, "text": "doc text"},),
        reference_document_ids={"syllabus": uuid4()},
        precomputed_context=precomputed,
    )
    assert execution._rubric("query", context) == ["itso-only-context"]
    assert execution._references("query", context) == ["syllabus-context"]


def test_precomputed_context_falls_back_when_source_type_missing(
    monkeypatch,
) -> None:
    """Fall back to live retrieval when source type is not precomputed."""
    from server.modules.agents.itso import execution
    from server.modules.agents.runtime.context import ITSOExecutionContext

    monkeypatch.setattr(
        execution,
        "retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("live-retrieved")],
    )
    monkeypatch.setattr(
        execution, "resolve_collection_name", lambda source_type: source_type
    )

    # Precomputed dict is missing the agent's rubric source type.
    precomputed = {
        "rubric_coord": ["other-context"],
    }

    monkeypatch.setattr(execution, "resolve_rubric_agent_id", lambda _: "sme")
    monkeypatch.setattr(
        execution, "get_active_rubric_context", lambda _: ["live-rubric"]
    )
    context = ITSOExecutionContext(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=({"chunk_id": "c1", "page_number": 1, "text": "doc text"},),
        reference_document_ids={"syllabus": uuid4()},
        precomputed_context=precomputed,
    )
    assert execution._rubric("query", context) == ["live-rubric"]
    assert execution._references("query", context) == ["live-retrieved"]
