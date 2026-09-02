"""Tests for the Coordinator envelope response schema, parser, and grounding."""

from __future__ import annotations

import json
import uuid

import pytest
from server.modules.agents.coordinator.response import (
    parse_and_validate_envelope_response,
)
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
)

SOURCE = "Objective: explain photosynthesis. Objective: describe cell walls."
CURRICULUM = "Unit 2 covers photosynthesis and light reactions in detail."


def make_criterion(code: str, *, strategy: str) -> CriterionDefinition:
    """Local builder standing in for the absent shared test helper."""
    if strategy == "curriculum_alignment":
        config = CurriculumAlignmentConfig()
    elif strategy == "count_band":
        config = CountBandConfig(
            mode="minimum_count", threshold_4=4, threshold_3=2, threshold_2=1
        )
    else:  # pragma: no cover - guard for typos
        raise ValueError(f"unknown strategy {strategy!r}")

    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=f"{code} title",
        description=f"{code} description",
        display_order=0,
        strategy_config=config,
    )


def _wrap(measurements):
    return json.dumps({"summary": "ok", "criterion_measurements": measurements})


def test_curriculum_alignment_grounded_row_kept():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    raw = _wrap([{
        "criterion_id": "A-05",
        "criterion_title": crit.title,
        "alignments": [{
            "objective_text": "Objective: explain photosynthesis.",
            "is_aligned": True,
            "assessment_excerpt": "Unit 2 covers photosynthesis and light reactions",
            "reasoning": "direct topic match",
        }],
    }])
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    m = out["criterion_measurements"][0]
    assert m["alignments"][0]["is_aligned"] is True
    assert m["_grounding_rejected_count"] == 0


def test_curriculum_alignment_ungrounded_row_demoted():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    raw = _wrap([{
        "criterion_id": "A-05",
        "criterion_title": crit.title,
        "alignments": [{
            "objective_text": "Objective: describe cell walls.",
            "is_aligned": True,
            "assessment_excerpt": "Curriculum discusses mitochondria at length",
            "reasoning": "made up",
        }],
    }])
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    m = out["criterion_measurements"][0]
    assert m["alignments"][0]["is_aligned"] is False
    assert m["alignments"][0]["assessment_excerpt"] is None
    assert m["_grounding_rejected_count"] == 1


def test_objective_text_not_in_source_rejected():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    raw = _wrap([{
        "criterion_id": "A-05",
        "criterion_title": crit.title,
        "alignments": [{
            "objective_text": "Objective: fabricate quantum tunneling.",
            "is_aligned": False,
            "assessment_excerpt": None,
        }],
    }])
    with pytest.raises(AgentExecutionError):
        parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)


def test_non_curriculum_criteria_still_validated_like_sme():
    crit = make_criterion("OP-02", strategy="count_band")
    raw = _wrap([{
        "criterion_id": "OP-02",
        "criterion_title": crit.title,
        "instances": [{"excerpt": "Objective: explain photosynthesis."}],
    }])
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    assert out["criterion_measurements"][0]["instances"][0]["excerpt"] in SOURCE
