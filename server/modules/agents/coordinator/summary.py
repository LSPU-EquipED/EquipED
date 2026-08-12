from __future__ import annotations

from ..contracts import CriterionScore


def _build_alignment_summary(criterion_scores: tuple[CriterionScore, ...]) -> str:
    """Build the Coordinator summary without another model invocation."""
    a05 = next((c for c in criterion_scores if c.criterion_id == "A-05"), None)
    return f"Objective-curriculum alignment: {a05.justification}" if a05 else ""


__all__ = ["_build_alignment_summary"]
