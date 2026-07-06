"""Tests for SME.run() as the engine's sole/unconditional scoring path.

SME no longer calls the shared ``BaseAgent.run()`` LLM-guesses-everything
flow at all -- the code-side engine (``registry.run_grouped`` /
``registry.run_criterion``) is the only scorer. These tests lock in the three
behaviors that matter: full success via the grouped pass, per-criterion
fallback when a basket is missing a code, and a hard failure when a code
fails both paths.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.scoring import registry
from server.modules.agents.sme import SME


class SequencedFakeClient:
    """Returns one canned payload per call, in call order.

    ``responses`` entries are dicts (JSON-encoded and returned) or ``None``
    (the call raises, simulating a basket/criterion extraction failure).
    Calling past the end of ``responses`` fails the test loudly rather than
    silently returning something misleading.
    """

    def __init__(self, responses: list[dict[str, Any] | None]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, **_: object) -> str:
        if self.calls >= len(self.responses):
            raise AssertionError(
                f"LLM called more times than expected (call #{self.calls + 1})"
            )
        payload = self.responses[self.calls]
        self.calls += 1
        if payload is None:
            raise RuntimeError("configured to fail")
        return json.dumps(payload)


# One valid payload per basket, in the fixed order ``run_grouped`` calls them
# (A1, A2, A3, A4, B1, B2) -- see registry._BASKETS.
_BASKET_A1 = {
    "objectives": [{"id": 1}],
    "assessments": [
        {"id": 1, "assessment_type": "objective_test", "evidence": "Q1"}
    ],
    "alignment": [{"objective_id": 1, "is_measured": True, "evidence": "Q1"}],
}
_BASKET_A2 = {
    "tasks": [
        {
            "text": "Task 1",
            "bloom_level": "apply",
            "directions": "Do X.",
            "has_clear_directions": True,
            "evidence": "Do X.",
        }
    ],
}
_BASKET_A3 = {
    "monitoring_mechanisms": [
        {"text": "Check 1", "monitoring_type": "checkpoint", "evidence": "quiz"}
    ],
}
_BASKET_A4 = {
    "enhancement_activities": [{"text": "Extra", "evidence": "Research more."}],
}
_BASKET_B1 = {
    "topics": [{"id": 1, "title": "T1"}, {"id": 2, "title": "T2"}],
    "transitions": [
        {"from_id": 1, "to_id": 2, "is_coherent": True, "reason": "ok"}
    ],
    "feedback_mechanisms": [
        {"text": "Key", "feedback_type": "answer_key", "evidence": "p.1"}
    ],
}
_BASKET_B2 = {
    "sections": [{"id": 1, "title": "S1", "is_clean": True, "issue": ""}],
}

_ALL_BASKETS_IN_ORDER = [
    _BASKET_A1, _BASKET_A2, _BASKET_A3, _BASKET_A4, _BASKET_B1, _BASKET_B2,
]

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
        "server.modules.agents.sme.get_active_rubric_criteria",
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
    assert result.summary == ""
    scored_codes = {s.criterion_id for s in result.criterion_scores}
    assert scored_codes == registry.REGISTERED_CODES
    for score in result.criterion_scores:
        assert 1 <= score.score <= 4
        assert score.chunk_ids == ()
        assert score.criterion_title == f"{score.criterion_id} Title"
    assert result.subtotal == sum(s.score for s in result.criterion_scores) / 10
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
