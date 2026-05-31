"""Tests for supervisor orchestration, pacing, delays, and precomputed context."""

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


def test_supervisor_pacing_skips_first_and_final_agent(
    monkeypatch, db_session,
) -> None:
    """Pacing sleep happens before agents 2..N, not before agent 1 or after last."""
    _seed_active_prompts(db_session)
    prompt_row = db_session.query(PromptVersion).filter_by(agent_id="sme").one()

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("server.modules.agents.supervisor.time.sleep", fake_sleep)
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_active_prompt",
        lambda agent_id, db: prompt_row,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_settings",
        lambda: type(
            "Settings", (), {"llm_agent_delay_seconds": 30},
        )(),
    )

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
    ]

    supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
    )

    # With only 1 agent, there should be NO sleep at all.
    assert sleep_calls == []


def test_supervisor_pacing_with_multiple_agents(monkeypatch, db_session) -> None:
    """With N agents, pacing should sleep N-1 times (before agents 2..N)."""
    _seed_active_prompts(db_session)
    prompt_row = db_session.query(PromptVersion).filter_by(agent_id="sme").one()

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("server.modules.agents.supervisor.time.sleep", fake_sleep)
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_active_prompt",
        lambda agent_id, db: prompt_row,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_settings",
        lambda: type(
            "Settings", (), {"llm_agent_delay_seconds": 15},
        )(),
    )

    agents = [_BatchAgent() for _ in range(4)]
    supervisor = Supervisor(agents=agents, db=db_session)

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
    ]

    supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
    )

    # 4 agents -> 3 sleeps (before agents 2, 3, 4), not 4.
    assert len(sleep_calls) == 3
    assert all(s == 15 for s in sleep_calls)


# ------------------------------------------------------------------
# Per-agent delay configuration tests
# ------------------------------------------------------------------

def test_per_agent_delay_config_parses_json(monkeypatch) -> None:
    """LLM_AGENT_DELAY_PER_AGENT should parse as a JSON dict."""
    from server.core import config as _config_mod
    from server.core.config import get_settings

    _config_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_AGENT_DELAY_PER_AGENT", '{"itso": 20, "gad": 5}')
    try:
        settings = get_settings()
        assert settings.llm_agent_delay_per_agent == {"itso": 20, "gad": 5}
    finally:
        get_settings.cache_clear()


def test_per_agent_delay_config_defaults_empty(monkeypatch) -> None:
    """Without env var, llm_agent_delay_per_agent should be empty dict."""
    from server.core import config as _config_mod
    from server.core.config import get_settings

    _config_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_AGENT_DELAY_PER_AGENT", "")
    try:
        settings = get_settings()
        assert settings.llm_agent_delay_per_agent == {}
    finally:
        get_settings.cache_clear()


def test_per_agent_delay_config_rejects_non_dict(monkeypatch) -> None:
    """LLM_AGENT_DELAY_PER_AGENT must be a JSON object, not array."""
    from server.core import config as _config_mod
    from server.core.config import get_settings
    from server.core.exceptions import ConfigurationError

    _config_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_AGENT_DELAY_PER_AGENT", '[20, 5]')
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "must be a JSON object" in str(exc)
    finally:
        get_settings.cache_clear()


def test_per_agent_delay_config_rejects_non_int_values(monkeypatch) -> None:
    """Values in LLM_AGENT_DELAY_PER_AGENT must be integers."""
    from server.core import config as _config_mod
    from server.core.config import get_settings
    from server.core.exceptions import ConfigurationError

    _config_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_AGENT_DELAY_PER_AGENT", '{"itso": "fast"}')
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "must be an integer" in str(exc)
    finally:
        get_settings.cache_clear()


def test_supervisor_uses_per_agent_delay(monkeypatch, db_session) -> None:
    """Supervisor should use per-agent delay when configured."""
    _seed_active_prompts(db_session)
    prompt_row = db_session.query(PromptVersion).filter_by(agent_id="sme").one()

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("server.modules.agents.supervisor.time.sleep", fake_sleep)
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_active_prompt",
        lambda agent_id, db: prompt_row,
    )
    # Per-agent: itso=20, gad=5, others fall back to global=10
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_settings",
        lambda: type(
            "Settings", (),
            {
                "llm_agent_delay_seconds": 10,
                "llm_agent_delay_per_agent": {"itso": 20, "gad": 5},
            },
        )(),
    )

    # Create agents with known names in order: sme, coordinator, gad, itso
    agents = [_BatchAgent() for _ in range(4)]
    agents[0].agent_name = "sme"
    agents[1].agent_name = "coordinator"
    agents[2].agent_name = "gad"
    agents[3].agent_name = "itso"

    supervisor = Supervisor(agents=agents, db=db_session)

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
    ]

    supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
    )

    # 4 agents -> 3 sleeps: coordinator(10), gad(5), itso(20)
    assert len(sleep_calls) == 3
    assert sleep_calls[0] == 10   # coordinator uses global fallback
    assert sleep_calls[1] == 5    # gad uses per-agent override
    assert sleep_calls[2] == 20   # itso uses per-agent override


def test_supervisor_falls_back_to_global_delay(monkeypatch, db_session) -> None:
    """When per-agent dict is empty, supervisor uses global delay."""
    _seed_active_prompts(db_session)
    prompt_row = db_session.query(PromptVersion).filter_by(agent_id="sme").one()

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr("server.modules.agents.supervisor.time.sleep", fake_sleep)
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_active_prompt",
        lambda agent_id, db: prompt_row,
    )
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_settings",
        lambda: type(
            "Settings", (),
            {
                "llm_agent_delay_seconds": 15,
                "llm_agent_delay_per_agent": {},
            },
        )(),
    )

    agents = [_BatchAgent() for _ in range(3)]
    for i, name in enumerate(["sme", "coordinator", "gad"]):
        agents[i].agent_name = name

    supervisor = Supervisor(agents=agents, db=db_session)

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
    ]

    supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
    )

    # 3 agents -> 2 sleeps, both using global 15s
    assert len(sleep_calls) == 2
    assert all(s == 15 for s in sleep_calls)
