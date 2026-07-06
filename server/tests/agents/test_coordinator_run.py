"""Tests for Coordinator.run() -- independent engine scoring.

Coordinator's rubric is identical to SME's (see
server/data/rubrics/rubrics.json), but Coordinator runs its own full engine
scoring independently rather than reusing SME's results. These tests lock in:
the engine computes independently, the usual chunk/text guards apply.
"""

from __future__ import annotations

import uuid

import pytest
from server.modules.agents.coordinator import Coordinator
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.scoring import registry

from .test_sme_run import _ALL_BASKETS_IN_ORDER, SequencedFakeClient

_TITLES = {code: f"{code} Coordinator Title" for code in registry.REGISTERED_CODES}

_CHUNK_INFOS = [{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}]


def _make_agent(monkeypatch, client) -> Coordinator:
    agent = Coordinator(llm_client=client)
    monkeypatch.setattr(
        Coordinator, "_load_document_text", lambda self, document_id: None
    )
    monkeypatch.setattr(
        "server.modules.agents.engine_scoring.get_active_rubric_criteria",
        lambda agent_id, db=None: _TITLES,
    )
    return agent


def test_computes_independently(monkeypatch) -> None:
    client = SequencedFakeClient(list(_ALL_BASKETS_IN_ORDER))
    agent = _make_agent(monkeypatch, client)

    result = agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="full slm text",
    )

    assert result.success is True
    scored_codes = {s.criterion_id for s in result.criterion_scores}
    assert scored_codes == registry.REGISTERED_CODES
    assert client.calls == 6


def test_fallback_raises_when_code_fails_both_engine_paths(monkeypatch) -> None:
    responses = list(_ALL_BASKETS_IN_ORDER)
    responses[2] = None  # A3 basket fails
    responses.append(None)  # per-criterion fallback for A-03 also fails
    client = SequencedFakeClient(responses)
    agent = _make_agent(monkeypatch, client)

    with pytest.raises(AgentExecutionError):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=_CHUNK_INFOS,
            context_text="full slm text",
        )


def test_raises_when_no_chunk_infos(monkeypatch) -> None:
    agent = _make_agent(monkeypatch, SequencedFakeClient([]))

    with pytest.raises(AgentExecutionError):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=[],
            context_text="full slm text",
        )
