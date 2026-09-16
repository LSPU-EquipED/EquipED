"""Tests for GAD registry scoring of llm_rubric_guidance criteria."""

from __future__ import annotations

import uuid

import pytest
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.agents.gad.registry import score_from_combined
from server.modules.rubrics.contracts import (
    CriterionDefinition,
    DomainDefinition,
    FormDefinition,
    LlmRubricGuidanceConfig,
    LlmScoreDescriptor,
)
from server.modules.rubrics.snapshot_contracts import build_evaluation_form_snapshot

_CHUNKS = [
    {
        "chunk_id": "chunk_1",
        "text": "Women are inherently too emotional for leadership.",
    }
]


def _snapshot_with_one_criterion():
    crit = CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="GAD-01",
        title="Free from Stereotypes",
        description="Judge freedom from gender stereotypes.",
        display_order=1,
        strategy_config=LlmRubricGuidanceConfig(
            guidance="Judge how free the material is from gender stereotypes.",
            level_descriptors=(
                LlmScoreDescriptor(
                    score=4,
                    descriptor=(
                        "No gender stereotypes or biased portrayals found "
                        "anywhere in the material."
                    ),
                ),
                LlmScoreDescriptor(
                    score=3,
                    descriptor=(
                        "At most one isolated instance of gender "
                        "stereotyping or bias."
                    ),
                ),
                LlmScoreDescriptor(
                    score=2,
                    descriptor=(
                        "A few instances of gender stereotyping or bias, "
                        "but not pervasive."
                    ),
                ),
                LlmScoreDescriptor(score=1, descriptor="Frequent or pervasive."),
            ),
        ),
    )
    form = FormDefinition(
        rubric_set_id=uuid.uuid4(),
        agent_id="gad",
        name="GAD Rubric v2",
        version_number=2,
        adapter_key="gad",
        adapter_version=2,
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid.uuid4(),
                code="GAD",
                title="Inclusivity & Gender Sensitivity",
                display_order=1,
                criteria=(crit,),
            ),
        ),
    )
    return build_evaluation_form_snapshot(uuid.uuid4(), form)


def test_score_from_combined_scores_grounded_llm_rubric_guidance() -> None:
    snapshot = _snapshot_with_one_criterion()
    combined = {
        "gad-01": {
            "score": 2,
            "evidence": "Women are inherently too emotional for leadership.",
            "chunk_id": "chunk_1",
            "reasoning": "Direct stereotype statement.",
        }
    }
    scores, candidates, accepted, rejected = score_from_combined(
        combined, _CHUNKS, form_snapshot=snapshot
    )
    assert len(scores) == 1
    assert scores[0].score == 2
    assert scores[0].chunk_ids == ("chunk_1",)
    assert scores[0].evidence == (
        "Women are inherently too emotional for leadership.",
    )
    assert candidates == 1
    assert accepted == 1
    assert rejected == 0


def test_score_from_combined_rejects_ungrounded_evidence() -> None:
    snapshot = _snapshot_with_one_criterion()
    combined = {
        "gad-01": {
            "score": 2,
            "evidence": "This exact sentence is not in the chunk.",
            "chunk_id": "chunk_1",
        }
    }
    with pytest.raises(AgentExecutionError, match="not grounded"):
        score_from_combined(combined, _CHUNKS, form_snapshot=snapshot)


def test_score_from_combined_rejects_unknown_chunk_id() -> None:
    snapshot = _snapshot_with_one_criterion()
    combined = {
        "gad-01": {
            "score": 2,
            "evidence": "Women are inherently too emotional for leadership.",
            "chunk_id": "does_not_exist",
        }
    }
    with pytest.raises(AgentExecutionError, match="not grounded"):
        score_from_combined(combined, _CHUNKS, form_snapshot=snapshot)
