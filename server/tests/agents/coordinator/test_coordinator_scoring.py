"""Tests for Coordinator curriculum-alignment scoring."""

from __future__ import annotations

import uuid
from typing import Any

from server.modules.agents.coordinator.scoring import (
    score_criterion_measurement,
    score_curriculum_alignment,
)
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
)

_CONFIGS: dict[str, Any] = {
    "curriculum_alignment": lambda: CurriculumAlignmentConfig(),
    "count_band": lambda: CountBandConfig(
        mode="minimum_count", threshold_4=4, threshold_3=2, threshold_2=1
    ),
}


def make_criterion(code: str, *, strategy: str = "curriculum_alignment"):
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=f"{code} title",
        description=f"{code} description",
        display_order=0,
        strategy_config=_CONFIGS[strategy](),
    )


def _alignments(total: int, aligned: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(total):
        is_aligned = i < aligned
        rows.append(
            {
                "objective_text": f"Objective {i}",
                "is_aligned": is_aligned,
                "assessment_excerpt": f"excerpt {i}" if is_aligned else None,
            }
        )
    return rows


def test_all_aligned_scores_4():
    crit = make_criterion("A-05")
    result = score_curriculum_alignment(crit, {"alignments": _alignments(10, 10)})
    assert result.score == 4
    assert result.criterion_id == "A-05"


def test_half_aligned_scores_3():
    crit = make_criterion("A-05")
    result = score_curriculum_alignment(crit, {"alignments": _alignments(10, 5)})
    assert result.score == 3


def test_low_alignment_scores_1():
    crit = make_criterion("A-05")
    result = score_curriculum_alignment(crit, {"alignments": _alignments(10, 1)})
    assert result.score == 1


def test_zero_objectives_scores_1():
    crit = make_criterion("A-05")
    result = score_curriculum_alignment(crit, {"alignments": []})
    assert result.score == 1
    assert "no objectives found" in result.justification


def test_justification_reports_rejected_count():
    crit = make_criterion("A-05")
    result = score_curriculum_alignment(
        crit,
        {"alignments": _alignments(10, 8), "_grounding_rejected_count": 3},
    )
    assert "3 unsupported claim(s) rejected" in result.justification


def test_count_band_still_routes_to_shared_calculator():
    crit = make_criterion("OP-02", strategy="count_band")
    measurement = {
        "instances": [
            {"excerpt": f"instance {i}", "explanation": None, "location": None}
            for i in range(4)
        ]
    }
    result = score_criterion_measurement(crit, measurement)
    assert result.score == 4
