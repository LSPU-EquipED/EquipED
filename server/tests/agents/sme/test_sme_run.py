"""Tests for SME.run() as the engine's sole/unconditional scoring path.

SME no longer uses the generic LLM-guesses-everything execution path;
flow at all -- the code-side engine (``registry.run_grouped`` /
``registry.run_criterion``) is the only scorer. These tests lock in the three
behaviors that matter: full success via the grouped pass, per-criterion
fallback when a basket is missing a code, and a hard failure when a code
fails both paths.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.runtime import llm as runtime_llm
from server.modules.agents.sme import registry
from server.modules.agents.sme.agent import SME
from server.tests.agents.helpers import _ALL_BASKETS_IN_ORDER, SequencedFakeClient

# The per-criterion fallback payload for A-03 (progress_monitoring.evaluate
# reads "mechanisms", not the basket's "monitoring_mechanisms").
_A03_FALLBACK = {
    "mechanisms": [
        {"text": "Check 1", "monitoring_type": "checkpoint", "evidence": "quiz"}
    ]
}

_TITLES = {code: f"{code} Title" for code in registry.REGISTERED_CODES}

_CHUNK_INFOS = [{"chunk_id": "chunk-1", "page_number": 1, "text": "SLM chunk"}]


def _make_agent(monkeypatch, client: Any) -> SME:
    agent = SME(llm_client=client)
    # Force the context_text fallback path instead of hitting a real DB/PDF.
    monkeypatch.setattr(SME, "_load_document_text", lambda self, document_id: None)
    monkeypatch.setattr(
        "server.modules.agents.sme.pipeline.get_active_rubric_criteria",
        lambda agent_id, db=None: _TITLES,
    )
    return agent


def test_full_success_scores_all_ten_from_grouped_pass(monkeypatch) -> None:
    client = SequencedFakeClient(list(_ALL_BASKETS_IN_ORDER))
    agent = _make_agent(monkeypatch, client)

    result = agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="full slm text",
    )

    assert result.success is True
    # Summary is now a deterministic, code-computed positive-then-improve
    # sentence pair -- not empty (see sme._build_improvement_summary).
    assert result.summary != ""
    assert "strongest area" in result.summary
    assert "consider" in result.summary
    scored_codes = {s.criterion_id for s in result.criterion_scores}
    assert scored_codes == registry.REGISTERED_CODES
    for score in result.criterion_scores:
        assert 1 <= score.score <= 4
        assert score.chunk_ids == ()
        assert score.criterion_title == f"{score.criterion_id} Title"
    assert result.subtotal == sum(s.score for s in result.criterion_scores) / 10
    assert result.advisory_outputs is None
    # Exactly 6 basket calls, no fallback needed.
    assert client.calls == 6


def test_missing_basket_falls_back_to_per_criterion(monkeypatch) -> None:
    responses = list(_ALL_BASKETS_IN_ORDER)
    responses[2] = None  # A3 basket fails -> A-03 missing from the grouped pass
    responses.append(_A03_FALLBACK)  # 7th call: per-criterion fallback for A-03
    client = SequencedFakeClient(responses)
    agent = _make_agent(monkeypatch, client)

    result = agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="full slm text",
    )

    assert result.success is True
    by_id = {s.criterion_id: s for s in result.criterion_scores}
    assert set(by_id) == registry.REGISTERED_CODES
    # A-03 still scored -- via the per-criterion fallback, not the basket.
    assert by_id["A-03"].score == 2  # 1 genuine mechanism -> band 2
    assert client.calls == 7


def test_code_failing_both_paths_raises(monkeypatch) -> None:
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


def test_model_name_falls_back_to_default(monkeypatch) -> None:
    from server.core.llm import get_llm_model_name

    client = SequencedFakeClient(list(_ALL_BASKETS_IN_ORDER))
    agent = _make_agent(monkeypatch, client)
    result = agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="full slm text",
    )
    assert result.model_name == get_llm_model_name()


def test_model_name_uses_client_model(monkeypatch) -> None:
    client = SequencedFakeClient(list(_ALL_BASKETS_IN_ORDER))
    client.model = "sme-custom-test-model"
    agent = _make_agent(monkeypatch, client)
    result = agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="full slm text",
    )
    assert result.model_name == "sme-custom-test-model"


def test_persistent_primary_uses_global_fallback_for_grouped_run(monkeypatch) -> None:
    class FailingPrimary:
        model = "primary-sme-model"

        def generate(self, prompt: str, **_: object) -> str:
            raise RuntimeError("HTTP 429 assigned provider unavailable")

    class HealthyFallback(SequencedFakeClient):
        model: str = "healthy-fallback-model"

    fallback = HealthyFallback(list(_ALL_BASKETS_IN_ORDER))
    monkeypatch.setattr(runtime_llm, "get_llm_client", lambda: fallback)
    agent = _make_agent(monkeypatch, FailingPrimary())

    result = agent.run(
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_infos=_CHUNK_INFOS,
        context_text="full slm text",
    )

    assert result.success is True
    assert result.model_name == "healthy-fallback-model"
    assert result.provenance == {
        "requested_model": "primary-sme-model",
        "actual_model": "healthy-fallback-model",
        "fallback_occurred": True,
    }
    assert {
        score.criterion_id for score in result.criterion_scores
    } == registry.REGISTERED_CODES
    assert result.error_message is None
    assert "HTTP 429" not in (result.raw_response or "")
    assert fallback.calls == 6


def test_raises_when_no_chunk_infos(monkeypatch) -> None:
    agent = _make_agent(monkeypatch, SequencedFakeClient([]))

    with pytest.raises(AgentExecutionError):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=[],
            context_text="full slm text",
        )


def test_raises_when_no_text_available(monkeypatch) -> None:
    agent = _make_agent(monkeypatch, SequencedFakeClient([]))

    with pytest.raises(AgentExecutionError):
        agent.run(
            evaluation_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_infos=[{"chunk_id": "chunk-1", "page_number": 1, "text": ""}],
            context_text="   ",
        )
