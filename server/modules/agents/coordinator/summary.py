"""Deterministic Coordinator result summary (no LLM invocation)."""

from __future__ import annotations

from ..contracts import CriterionScore

_WEAK_THRESHOLD = 2


def build_alignment_summary(criterion_scores: tuple[CriterionScore, ...]) -> str:
    """One-line deterministic summary of Coordinator's 10-criterion result."""
    if not criterion_scores:
        return ""
    a05 = next((c for c in criterion_scores if c.criterion_id == "A-05"), None)
    weak = sorted(
        (c for c in criterion_scores if c.score <= _WEAK_THRESHOLD),
        key=lambda c: c.score,
    )
    parts: list[str] = []
    if a05 is not None:
        parts.append(f"Curriculum alignment (A-05) scored {a05.score}/4.")
    if weak:
        titles = ", ".join(c.criterion_title for c in weak)
        parts.append(f"Weakest areas: {titles}.")
    else:
        parts.append("No criteria scored below 3.")
    return " ".join(parts)


__all__ = ["build_alignment_summary"]
