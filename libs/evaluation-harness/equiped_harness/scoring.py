"""Supported semantic scoring helpers shared with backend result consumers."""

from .result_contracts import (
    AgentEvaluationResult,
    CoordinatorAlignmentAdvisory,
    CurriculumObjectiveMatch,
)
from .runtime.bands import RatioBand, count_band, mean_band, ratio_band
from .sme.scoring import score_criterion_measurement


def validate_score_band(score: int) -> int:
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 4:
        raise ValueError("criterion score out of bounds")
    return score


__all__ = [
    "score_criterion_measurement",
    "RatioBand",
    "ratio_band",
    "count_band",
    "mean_band",
    "validate_score_band",
    "validate_coordinator_coverage",
]


def validate_coordinator_coverage(result: AgentEvaluationResult) -> None:
    """Validate v3 official A-05 and advisory C-01 against frozen measurements."""
    advisory = CoordinatorAlignmentAdvisory.from_dict(result.advisory_outputs.to_dict())
    rows = (
        (result.metadata.get("group_responses") or {})
        .get("envelope_2", {})
        .get("objective_matches")
    )
    if not isinstance(rows, list) or len(rows) != len(advisory.objective_matches):
        raise ValueError("objective inventory mismatch")
    assessment_matches = []
    for row, c_match in zip(rows, advisory.objective_matches, strict=True):
        if not isinstance(row, dict) or set(row) != {
            "objective_id",
            "objective_text",
            "assessment_matched",
            "assessment_excerpt",
            "assessment_rejected",
            "curriculum_matched",
            "curriculum_excerpt",
            "curriculum_rejected",
        }:
            raise ValueError("invalid objective measurement fields")

        def match_for(dimension: str) -> CurriculumObjectiveMatch:
            return CurriculumObjectiveMatch(
                objective_id=row["objective_id"],
                objective_text=row["objective_text"],
                matched=row[f"{dimension}_matched"],
                excerpt=row[f"{dimension}_excerpt"],
                rejected=row[f"{dimension}_rejected"],
            )

        if match_for("curriculum") != c_match:
            raise ValueError("curriculum advisory disagrees with frozen measurement")
        assessment_matches.append(match_for("assessment"))
    a05 = next(s for s in result.criterion_scores if s.criterion_id == "A-05")
    derived_score = ratio_band(
        sum(m.matched for m in assessment_matches), len(rows)
    ).band
    if a05.score != derived_score or a05.evidence != tuple(
        m.excerpt for m in assessment_matches if m.matched
    ):
        raise ValueError("objective gauging disagrees with frozen measurement")
