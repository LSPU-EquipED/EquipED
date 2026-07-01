"""Registry of code-side scored SME criteria.

Single source of truth for "which criteria use the engine." Both the CLI
(server/scripts/score_criterion.py) and the SME agent read from here, so a
criterion is migrated in exactly one place. ``run_criterion`` runs a registered
criterion and returns the pieces the agent needs to build a ``CriterionScore``:
the 1-4 band, a human-readable justification, and the evidence quotes.

Scoped to SME only. The other agents (Coordinator/GAD/ITSO) are untouched.
"""

from __future__ import annotations

from typing import Any

from . import interactivity, objective_alignment

# Criterion codes handled by the engine. Anything not listed keeps the old
# LLM-picks-a-score path.
REGISTERED_CODES: frozenset[str] = frozenset({"A-05", "OP-02"})


def is_registered(criterion_code: str) -> bool:
    return criterion_code in REGISTERED_CODES


def run_criterion(
    criterion_code: str, client: Any, text: str
) -> tuple[int, str, tuple[str, ...]]:
    """Run one registered criterion against the full SLM text.

    Returns ``(score, justification, evidence)``. Raises ``KeyError`` for an
    unregistered code so callers must check ``is_registered`` first.
    """
    if criterion_code == "A-05":
        result = objective_alignment.evaluate(client, text)
        pct = f"{result.pct:.0f}%" if result.pct is not None else "n/a"
        justification = (
            f"Objective gauging (code-computed): {result.aligned} of "
            f"{result.total_objectives} objectives are measured by a real "
            f"assessment ({pct}); {result.total_assessments} assessment(s) "
            f"found. Score {result.score} on the moderate scale."
        )
        evidence = tuple(
            str(a.get("evidence", ""))
            for a in result.alignment
            if a.get("is_measured") and a.get("evidence")
        )
        return result.score, justification, evidence

    if criterion_code == "OP-02":
        result = interactivity.evaluate(client, text)
        justification = (
            f"Interactivity (code-computed): {result.count} genuine interactive "
            f"element(s) with real task content found. Score {result.score} "
            f"(4+ -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1)."
        )
        evidence = tuple(
            str(e.get("evidence", "")) for e in result.genuine if e.get("evidence")
        )
        return result.score, justification, evidence

    raise KeyError(f"criterion {criterion_code!r} is not registered")


__all__ = ["REGISTERED_CODES", "is_registered", "run_criterion"]
