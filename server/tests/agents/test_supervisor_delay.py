"""Tests for supervisor pacing and per-agent delay configuration."""

from __future__ import annotations

from uuid import uuid4

from server.modules.admin.models import PromptVersion
from server.modules.agents.supervisor import Supervisor
from server.modules.documents.models import DocumentChunk

from .conftest import (
    _BatchAgent,
    _seed_active_prompts,
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
    """With parallel execution, agents run concurrently — no sequential pacing."""
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

    result = supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
    )

    # Parallel execution: no sequential pacing between agents.
    assert sleep_calls == []
    assert len(result.agent_results) == 4


# ------------------------------------------------------------------
# Per-agent delay configuration tests
# ------------------------------------------------------------------

def test_per_agent_delay_config_parses_json(monkeypatch) -> None:
    """LLM_AGENT_DELAY_PER_AGENT should parse as a JSON dict."""
    from server.core import config as _config_mod
    from server.core.config import get_settings

    _config_mod.get_settings.cache_clear()
    # Pin chunk budget to be < total budget default (8,000) so the new
    # cross-field validation does not fire before the test assertion runs.
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")
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
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")
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
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")
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
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")
    monkeypatch.setenv("LLM_AGENT_DELAY_PER_AGENT", '{"itso": "fast"}')
    try:
        get_settings()
        raise AssertionError("expected ConfigurationError")
    except ConfigurationError as exc:
        assert "must be an integer" in str(exc)
    finally:
        get_settings.cache_clear()


def test_supervisor_uses_per_agent_delay(monkeypatch, db_session) -> None:
    """With parallel execution, per-agent delay settings are not applied between agents."""
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
    def _make_settings():
        def get_agent_temperature(_self, agent_name):
            return 0.2
        return type(
            "Settings", (),
            {
                "llm_agent_delay_seconds": 10,
                "llm_agent_delay_per_agent": {"itso": 20, "gad": 5},
                "llm_temperature": 0.2,
                "llm_temperature_itso": 0.0,
                "get_agent_temperature": get_agent_temperature,
            },
        )()
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_settings",
        _make_settings,
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

    result = supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
    )

    # Parallel execution: agents run concurrently, no sequential pacing.
    assert sleep_calls == []
    assert len(result.agent_results) == 4


def test_supervisor_falls_back_to_global_delay(monkeypatch, db_session) -> None:
    """With parallel execution, global delay is not applied between agents."""
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
    def _make_settings():
        def get_agent_temperature(_self, agent_name):
            return 0.2
        return type(
            "Settings", (),
            {
                "llm_agent_delay_seconds": 15,
                "llm_agent_delay_per_agent": {},
                "llm_temperature": 0.2,
                "llm_temperature_itso": 0.0,
                "get_agent_temperature": get_agent_temperature,
            },
        )()
    monkeypatch.setattr(
        "server.modules.agents.supervisor.get_settings",
        _make_settings,
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

    result = supervisor.run_evaluation(
        evaluation_id=uuid4(),
        document_id=uuid4(),
        chunks=chunks,
    )

    # Parallel execution: agents run concurrently, no sequential pacing.
    assert sleep_calls == []
    assert len(result.agent_results) == 3
