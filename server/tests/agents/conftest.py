"""Pytest fixtures for agent tests."""

from __future__ import annotations

import pytest
from server.tests.agents.helpers import _FakeLLM


@pytest.fixture(autouse=True)
def _isolate_agent_settings(monkeypatch) -> None:
    """Auto-applied fixture that pins every agent test to compatible
    prompt-budget env vars so the new cross-field validation in
    ``get_settings()`` (chunk budget must be less than total budget)
    does not fire mid-test.

    Strategy: set ``AGENT_PROMPT_BUDGET_CHARS=5000`` in the test
    environment. The new total-budget default (8,000) is strictly
    larger, so the cross-field check passes wherever ``get_settings()``
    is called — including the call chain
    ``agent.run() -> get_llm_model_name() -> get_settings()`` in
    ``server.core.llm`` that previously raised.

    We use env-var pinning rather than monkeypatching ``get_settings``
    because real-database tests (``db_session`` fixture) depend on
    ``get_settings()`` returning the real ``DATABASE_URL`` from the
    project's ``.env`` so the cached ``get_engine()`` /
    ``get_session_factory()`` chain can build a working engine.
    Patching ``get_settings`` in those tests would break the
    database lookup.
    """
    monkeypatch.setenv("AGENT_PROMPT_BUDGET_CHARS", "5000")


@pytest.fixture(autouse=True)
def _mock_llm_client_for_agent(monkeypatch) -> None:
    """Auto-applied fixture that mocks ``get_llm_client_for_agent`` for every
    agent test.

    The supervisor now calls ``get_llm_client_for_agent(agent_name)`` (from
    ``server.core.llm``) to obtain a per-agent LLM client.  Without this
    mock the real ``LocalLLMClient`` would be instantiated and attempt a
    real HTTP call to an LLM endpoint, causing the test to hang.

    We return a ``_FakeLLM`` that echoes a minimal valid JSON response so
    any agent (including real ``ITSO`` subclasses) can complete its
    LLM call in tests.
    """
    fake = _FakeLLM(
        {
            "summary": "test",
            "criterion_scores": [
                {"criterion_id": "c1", "score": 3, "justification": "ok"},
            ],
        }
    )
    monkeypatch.setattr(
        "server.modules.agents.supervision.dispatch.get_llm_client_for_agent",
        lambda _agent_name: fake,
    )
