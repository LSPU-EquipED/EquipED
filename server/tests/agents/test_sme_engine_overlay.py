"""Tests for the SME code-side scoring overlay (flag-gated engine)."""

from __future__ import annotations

import json
import types
import uuid

from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.sme import SME


class FakeClient:
    """Returns canned JSON depending on which criterion prompt is sent."""

    def generate(self, prompt: str, **_: object) -> str:
        if "interactive element" in prompt.lower():
            return json.dumps(
                {
                    "interactive_elements": [
                        {"text": "Try This", "evidence": "Solve for x."},
                        {"text": "Reflect", "evidence": "How did S&T shape history?"},
                    ]
                }
            )
        # A-05 objective-alignment shape.
        return json.dumps(
            {
                "objectives": [{"id": 1}, {"id": 2}],
                "assessments": [{"id": 1}],
                "alignment": [
                    {"objective_id": 1, "is_measured": True, "evidence": "quiz q1"}
                ],
            }
        )


def _result(scores: list[CriterionScore]) -> AgentEvaluationResult:
    return AgentEvaluationResult(
        agent_name="sme",
        evaluation_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        subtotal=0.0,
        criterion_scores=tuple(scores),
        summary="",
        model_name="test",
        processing_seconds=0.0,
        token_count=0,
    )


def _settings() -> object:
    return types.SimpleNamespace(sme_scoring_call_delay_seconds=0)


def test_overlay_replaces_registered_keeps_others() -> None:
    agent = SME(llm_client=FakeClient())
    result = _result(
        [
            CriterionScore("A-05", "Objective Gauging", 4, "old A-05"),
            CriterionScore("OP-02", "Interactivity", 1, "old OP-02"),
            CriterionScore("OP-01", "Topic Coherence", 2, "old OP-01"),
        ]
    )

    out = agent._overlay_engine_scores(result, "full slm text", _settings())
    by_id = {s.criterion_id: s for s in out.criterion_scores}

    # A-05: 1 of 2 objectives measured = 50% -> moderate band 3.
    assert by_id["A-05"].score == 3
    assert "quiz q1" in by_id["A-05"].evidence
    assert by_id["A-05"].chunk_ids == ()

    # OP-02: 2 genuine elements -> band 3.
    assert by_id["OP-02"].score == 3

    # OP-01 is not registered -> untouched.
    assert by_id["OP-01"].score == 2
    assert by_id["OP-01"].justification == "old OP-01"

    # Subtotal recomputed from the overlaid scores.
    assert out.subtotal == (3 + 3 + 2) / 3


def test_overlay_keeps_old_score_on_engine_error() -> None:
    class BrokenClient:
        def generate(self, prompt: str, **_: object) -> str:
            return "not json at all"

    agent = SME(llm_client=BrokenClient())
    result = _result([CriterionScore("A-05", "Objective Gauging", 4, "old A-05")])

    out = agent._overlay_engine_scores(result, "full slm text", _settings())
    # Engine blew up -> original score preserved, agent does not fail.
    assert out.criterion_scores[0].score == 4
    assert out.criterion_scores[0].justification == "old A-05"
