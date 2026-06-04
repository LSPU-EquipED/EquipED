"""Tests for supervisor orchestration and precomputed context."""

from __future__ import annotations

from uuid import uuid4

from server.modules.admin.models import PromptVersion
from server.modules.agents.supervisor import Supervisor
from server.modules.documents.models import DocumentChunk

from .conftest import (
    _BatchAgent,
    _FailingAgent,
    _RetrievedChunk,
    _seed_active_prompts,
)


def test_supervisor_passes_all_chunks_and_loads_active_prompts(
    monkeypatch, db_session
) -> None:
    _seed_active_prompts(db_session)
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
        "server.modules.agents.supervisor.get_active_prompt",
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
    failing_agent = _FailingAgent()
    success_agent = _BatchAgent()
    supervisor = Supervisor(agents=[failing_agent, success_agent], db=db_session)

    prompt_rows = {
        agent_id: db_session.query(PromptVersion).filter_by(agent_id=agent_id).one()
        for agent_id in ["coordinator", "sme"]
    }

    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_active_prompt",
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
    assert result.failures == {"coordinator": "agent failed"}


def test_precomputed_context_respects_per_agent_rubric_scope(monkeypatch) -> None:
    """Each agent should only receive its own rubric context from precomputed dict."""
    from server.modules.agents.base import BaseAgent

    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("rubric context")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
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

    class _CapturingAgent(BaseAgent):
        agent_name = "sme"
        rubric_source_type = "rubric_sme"
        reference_source_types = ("syllabus",)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.captured_rubric = None
            self.captured_reference = None

        def _build_prompt(self, *, rubric_context, reference_context, **kw):
            self.captured_rubric = rubric_context
            self.captured_reference = reference_context
            return "{}"

    from .conftest import _FakeLLM

    agent = _CapturingAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        )
    )

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "doc text"}],
        context_text="query",
        reference_document_ids={"syllabus": uuid4()},
        precomputed_context=precomputed,
    )

    # Agent should only get its own rubric context, not all merged together.
    assert agent.captured_rubric == ["sme-only-context"]
    assert agent.captured_reference == ["syllabus-context"]


def test_precomputed_context_falls_back_when_source_type_missing(
    monkeypatch, db_session,
) -> None:
    """Fall back to live retrieval when source type is not precomputed."""
    from server.modules.agents.base import BaseAgent
    from server.modules.rubrics.models import RubricCriterion, RubricDomain, RubricSet

    monkeypatch.setattr(
        "server.modules.agents.base.retrieve_context",
        lambda *args, **kwargs: [_RetrievedChunk("live-retrieved")],
    )
    monkeypatch.setattr(
        "server.modules.agents.base.resolve_collection_name",
        lambda source_type: source_type,
    )

    # Precomputed dict is missing the agent's rubric source type.
    precomputed = {
        "rubric_coord": ["other-context"],
    }

    rubric_set = RubricSet(
        agent_id="sme",
        name="SME Rubric v1",
        version_number=1,
        status="active",
    )
    db_session.add(rubric_set)
    db_session.flush()
    domain = RubricDomain(
        rubric_set_id=rubric_set.rubric_set_id,
        code="OP",
        title="Organization & Presentation",
        display_order=1,
    )
    db_session.add(domain)
    db_session.flush()
    db_session.add(
        RubricCriterion(
            rubric_domain_id=domain.rubric_domain_id,
            criterion_code="OP-01",
            title="Topic Coherence",
            description="Topics are coherent from Unit to Chapter.",
            display_order=1,
        )
    )
    db_session.commit()

    class _CapturingAgent(BaseAgent):
        agent_name = "sme"
        rubric_source_type = "rubric_sme"
        reference_source_types = ()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.captured_rubric = None

        def _build_prompt(self, *, rubric_context, **kw):
            self.captured_rubric = rubric_context
            return "{}"

    from .conftest import _FakeLLM

    agent = _CapturingAgent(
        llm_client=_FakeLLM(
            {
                "summary": "ok",
                "criterion_scores": [
                    {"criterion_id": "c1", "score": 3, "justification": "ok"},
                ],
            }
        )
    )

    agent.run(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunk_infos=[{"chunk_id": "c1", "page_number": 1, "text": "doc text"}],
        precomputed_context=precomputed,
    )

    assert agent.captured_rubric[0] == "[SME Rubric v1]"
    assert "Domain: Organization & Presentation" in agent.captured_rubric
    assert (
        "OP-01 | Title: Topic Coherence | Description: Topics are coherent from Unit to Chapter."
        in agent.captured_rubric
    )
