"""Tests for SME.run() as the grouped-LLM-scoring sole scoring path.

SME scores every criterion with 3 grouped direct-LLM calls (see
``sme/groups.py`` + ``sme/grouped_execution.py``); the code-side engine's
per-criterion lane (``registry.run_criterion``) is retained only as the
fallback for a group whose grouped call fails. These tests lock in the three
behaviors that matter: full success via the grouped calls, per-criterion
fallback when one group fails, and a hard failure when a code fails both paths.
"""

from __future__ import annotations

import uuid

import pytest
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.sme import registry
from server.modules.agents.sme.agent import SME
from server.tests.agents.helpers import (
    SME_CRITERION_FALLBACKS,
    SME_GROUP_TITLES,
    GroupScoringFakeClient,
    sme_group_payloads,
)

_TITLES = dict(SME_GROUP_TITLES)

_CHUNK_INFOS = [{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}]

# ``assessment_alignment`` is scored first and covers A-02 then A-05, so a
# failure of that group consumes exactly these two per-criterion fallbacks.
_ASSESSMENT_FALLBACKS = [
    SME_CRITERION_FALLBACKS["A-02"],
    SME_CRITERION_FALLBACKS["A-05"],
]


def _make_agent(monkeypatch, client) -> SME:
    agent = SME(llm_client=client)
    monkeypatch.setattr(
        "server.modules.agents.sme.pipeline.get_active_rubric_criteria",
        lambda agent_id, db=None: _TITLES,
    )
    monkeypatch.setattr(
        "server.modules.agents.sme.pipeline.get_active_rubric_descriptions",
        lambda agent_id, db=None: {},
    )
    return agent


def _run(agent: SME):
    return agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="full slm text",
        canonical_source_text="canonical SLM text",
    )


def test_full_success_scores_all_ten_from_grouped_calls(monkeypatch) -> None:
    client = GroupScoringFakeClient(sme_group_payloads(2))
    agent = _make_agent(monkeypatch, client)

    result = _run(agent)

    assert result.success is True
    # Summary is a deterministic, code-computed positive-then-improve sentence
    # pair -- not empty (see sme._build_improvement_summary).
    assert result.summary != ""
    assert "strongest area" in result.summary
    assert "consider" in result.summary
    scored_codes = {s.criterion_id for s in result.criterion_scores}
    assert scored_codes == registry.REGISTERED_CODES
    for score in result.criterion_scores:
        assert 1 <= score.score <= 4
        assert score.chunk_ids == ()
        assert score.criterion_title == _TITLES[score.criterion_id]
    assert result.subtotal == sum(s.score for s in result.criterion_scores) / 10
    assert result.advisory_outputs is None
    # Exactly 3 grouped calls, no fallback needed.
    assert client.group_calls == 3
    assert client.fallback_calls == 0
    assert set(result.metadata["group_prompts"]) == {
        "assessment_alignment",
        "task_execution",
        "document_wide",
    }


def test_failed_group_falls_back_to_per_criterion(monkeypatch) -> None:
    payloads = sme_group_payloads(3)
    payloads["assessment_alignment"] = None  # transport failure for that group
    client = GroupScoringFakeClient(payloads, list(_ASSESSMENT_FALLBACKS))
    agent = _make_agent(monkeypatch, client)

    result = _run(agent)

    assert result.success is True
    by_id = {s.criterion_id: s for s in result.criterion_scores}
    assert set(by_id) == registry.REGISTERED_CODES
    # A-02/A-05 still scored -- via the per-criterion engine lane, not the
    # grouped call, so their justification is the code-computed text.
    assert "code-computed" in by_id["A-02"].justification
    assert "code-computed" in by_id["A-05"].justification
    # ... while every other group kept the grouped LLM's own justification.
    assert by_id["OP-01"].justification == "justification"
    # 3 grouped attempts (one failing) + 2 per-criterion fallbacks.
    assert client.group_calls == 3
    assert client.fallback_calls == 2
    assert result.provenance["criterion_fallback_calls"] == 2
    assert "assessment_alignment" not in result.metadata["group_prompts"]


def test_code_failing_both_paths_raises(monkeypatch) -> None:
    payloads = sme_group_payloads(3)
    payloads["assessment_alignment"] = None
    # First per-criterion fallback (A-02) also fails.
    client = GroupScoringFakeClient(payloads, [None])
    agent = _make_agent(monkeypatch, client)

    with pytest.raises(AgentExecutionError, match="failed in both"):
        _run(agent)


def test_model_name_falls_back_to_default(monkeypatch) -> None:
    from server.core.llm import get_llm_model_name

    client = GroupScoringFakeClient(sme_group_payloads(3))
    agent = _make_agent(monkeypatch, client)
    result = _run(agent)
    assert result.model_name == get_llm_model_name()


def test_model_name_uses_client_model(monkeypatch) -> None:
    client = GroupScoringFakeClient(
        sme_group_payloads(3), model="sme-custom-test-model"
    )
    agent = _make_agent(monkeypatch, client)
    result = _run(agent)
    assert result.model_name == "sme-custom-test-model"


def test_persistent_primary_does_not_use_global_fallback(monkeypatch) -> None:
    class FailingPrimary:
        model = "primary-sme-model"

        def generate(self, prompt: str, **_: object) -> str:
            raise RuntimeError("HTTP 429 assigned provider unavailable")

    global_calls = 0

    def fail_if_called():
        nonlocal global_calls
        global_calls += 1
        raise AssertionError("global client must not be called")

    monkeypatch.setattr(
        "server.modules.agents.runtime.llm.get_llm_client", fail_if_called
    )
    agent = _make_agent(monkeypatch, FailingPrimary())

    with pytest.raises(AgentExecutionError) as raised:
        _run(agent)
    assert global_calls == 0
    assert "HTTP 429" not in str(raised.value)


def test_raises_when_no_chunk_infos(monkeypatch) -> None:
    agent = _make_agent(monkeypatch, GroupScoringFakeClient({}))

    with pytest.raises(AgentExecutionError):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=[],
            context_text="full slm text",
            canonical_source_text="canonical SLM text",
        )


def test_raises_when_no_text_available(monkeypatch) -> None:
    agent = _make_agent(monkeypatch, GroupScoringFakeClient({}))

    with pytest.raises(AgentExecutionError):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=[
                {"chunk_id": "chunk-1", "page_number": 1, "text": "chunk fallback"}
            ],
            context_text="context fallback",
            canonical_source_text=None,
        )
