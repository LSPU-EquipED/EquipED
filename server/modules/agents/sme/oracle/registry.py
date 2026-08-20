"""Registry of code-side scored SME criteria.

Single source of truth for "which criteria use the engine." Both the CLI
(server/scripts/score_criterion.py) and the SME agent read from here, so a
criterion is migrated in exactly one place. ``run_criterion`` runs a registered
criterion (its own per-criterion LLM call) and returns the pieces the agent
needs to build a ``CriterionScore``: the 1-4 band, a human-readable
justification, and the evidence quotes.

Scoped to SME only. The other agents (Coordinator/GAD/ITSO) are untouched.
"""

from __future__ import annotations

from typing import Any

from .....core.config import get_settings
from .....core.llm import ResponseContract
from ...runtime.llm import parse_json_payload
from . import (
    accurate_sections,
    clear_directions,
    enhancement_activities,
    interactivity,
    learner_transformation,
    objective_alignment,
    prescriptive_feedback,
    progress_monitoring,
    topic_coherence,
    varied_assessment,
)
from .criterion_contracts import RESPONSE_SCHEMAS, validate

# Criterion codes handled by the engine. Anything not listed keeps the old
# LLM-picks-a-score path.
REGISTERED_CODES: frozenset[str] = frozenset(
    {
        "A-01",
        "A-02",
        "A-03",
        "A-04",
        "A-05",
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
    }
)


def is_registered(criterion_code: str) -> bool:
    return criterion_code in REGISTERED_CODES


def _render(criterion_code: str, result: Any) -> tuple[int, str, tuple[str, ...]]:
    """Turn a criterion's ``compute()``/``evaluate()`` result into the
    ``(score, justification, evidence)`` tuple the agent needs.
    """
    if criterion_code == "A-05":
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
        justification = (
            f"Interactivity (code-computed): {result.count} genuine interactive "
            f"element(s) with real task content found. Score {result.score} "
            f"(4+ -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1)."
        )
        evidence = tuple(
            str(e.get("evidence", "")) for e in result.genuine if e.get("evidence")
        )
        return result.score, justification, evidence

    if criterion_code == "OP-03":
        pct = f"{result.pct:.0f}%" if result.pct is not None else "n/a"
        justification = (
            f"Clear directions (code-computed): {result.clear} of {result.total} "
            f"task(s) have clear, complete directions ({pct}). Score "
            f"{result.score} on the moderate scale."
        )
        evidence = tuple(
            str(t.get("directions", ""))
            for t in result.clear_tasks
            if t.get("directions")
        )
        return result.score, justification, evidence

    if criterion_code == "A-01":
        pct = f"{result.pct:.0f}%" if result.pct is not None else "n/a"
        justification = (
            f"Learner transformation (code-computed): {result.higher_order} of "
            f"{result.total} task(s) engage higher-order thinking "
            f"(apply/analyze/evaluate/create) ({pct}). Score {result.score} on "
            f"the moderate scale."
        )
        evidence = tuple(
            str(t.get("evidence", ""))
            for t in result.higher_order_tasks
            if t.get("evidence")
        )
        return result.score, justification, evidence

    if criterion_code == "A-02":
        justification = (
            f"Varied assessment tools (code-computed): {result.count} distinct "
            f"assessment type(s) found ({', '.join(result.types) or 'none'}). "
            f"Score {result.score} (5+ -> 4, 3-4 -> 3, 2 -> 2, <=1 -> 1)."
        )
        evidence = tuple(
            str(a.get("evidence", "")) for a in result.genuine if a.get("evidence")
        )
        return result.score, justification, evidence

    if criterion_code == "A-03":
        justification = (
            f"Progress monitoring (code-computed): {result.count} genuine "
            f"monitoring mechanism(s) found, spanning {len(result.types)} of 4 "
            f"type(s) ({', '.join(result.types) or 'none'}). Score "
            f"{result.score} (4+ -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1)."
        )
        evidence = tuple(
            str(m.get("evidence", "")) for m in result.genuine if m.get("evidence")
        )
        return result.score, justification, evidence

    if criterion_code == "A-04":
        justification = (
            f"Prescriptive feedback (code-computed): {result.count} distinct "
            f"feedback/intervention mechanism type(s) found "
            f"({', '.join(result.types) or 'none'}). Score {result.score} "
            f"(3-4 -> 4, 2 -> 3, 1 -> 2, 0 -> 1)."
        )
        evidence = tuple(
            str(m.get("evidence", "")) for m in result.genuine if m.get("evidence")
        )
        return result.score, justification, evidence

    if criterion_code == "OP-01":
        if result.mode == "issue-count":
            issues = result.total - result.coherent
            justification = (
                f"Topic coherence (code-computed): short document, "
                f"{result.total} transition(s) found with {issues} issue(s) "
                f"(issue-count fallback). Score {result.score} "
                f"(0 -> 4, 1 -> 3, 2 -> 2, 3+ -> 1)."
            )
        else:
            pct = f"{result.pct:.0f}%" if result.pct is not None else "n/a"
            justification = (
                f"Topic coherence (code-computed): {result.coherent} of "
                f"{result.total} transition(s) are coherent ({pct}). Score "
                f"{result.score} on the moderate scale."
            )
        evidence = tuple(
            str(t.get("reason", ""))
            for t in result.transitions
            if not t.get("is_coherent") and t.get("reason")
        )
        return result.score, justification, evidence

    if criterion_code == "OP-04":
        pct = f"{result.pct:.0f}%" if result.pct is not None else "n/a"
        justification = (
            f"Accurate sections (code-computed): {result.clean} of "
            f"{result.total} section(s) are clear and internally consistent "
            f"({pct}). Score {result.score} on the moderate scale."
        )
        evidence = tuple(
            str(s.get("issue", "")) for s in result.flagged if s.get("issue")
        )
        return result.score, justification, evidence

    if criterion_code == "OP-05":
        justification = (
            f"Enhancement activities (code-computed): {result.count} genuine "
            f"enhancement activity(ies) beyond the core found. Score "
            f"{result.score} (3+ -> 4, 2 -> 3, 1 -> 2, 0 -> 1)."
        )
        evidence = tuple(
            str(e.get("evidence", "")) for e in result.genuine if e.get("evidence")
        )
        return result.score, justification, evidence

    raise KeyError(f"criterion {criterion_code!r} is not registered")


def run_criterion(
    criterion_code: str, client: Any, text: str, *, prompt_preamble: str | None = None
) -> tuple[int, str, tuple[str, ...]]:
    """Run one registered criterion against the full SLM text (its own call).

    Returns ``(score, justification, evidence)``. Raises ``KeyError`` for an
    unregistered code so callers must check ``is_registered`` first.
    """
    client = _CriterionClient(client, prompt_preamble or "", criterion_code)
    if criterion_code == "A-05":
        result = objective_alignment.evaluate(client, text)
    elif criterion_code == "OP-02":
        result = interactivity.evaluate(client, text)
    elif criterion_code == "OP-03":
        result = clear_directions.evaluate(client, text)
    elif criterion_code == "A-01":
        result = learner_transformation.evaluate(client, text)
    elif criterion_code == "A-02":
        result = varied_assessment.evaluate(client, text)
    elif criterion_code == "A-03":
        result = progress_monitoring.evaluate(client, text)
    elif criterion_code == "A-04":
        result = prescriptive_feedback.evaluate(client, text)
    elif criterion_code == "OP-01":
        result = topic_coherence.evaluate(client, text)
    elif criterion_code == "OP-04":
        result = accurate_sections.evaluate(client, text)
    elif criterion_code == "OP-05":
        result = enhancement_activities.evaluate(client, text)
    else:
        raise KeyError(f"criterion {criterion_code!r} is not registered")

    return _render(criterion_code, result)


class _CriterionClient:
    def __init__(self, client: Any, preamble: str, code: str) -> None:
        self._client, self._preamble, self._code = client, preamble, code

    def generate(self, prompt: str, **kwargs: Any) -> str:
        if (
            len(self._preamble.rstrip() + "\n\n" + prompt)
            > get_settings().sme_total_prompt_budget_chars
        ):
            raise ValueError("criterion prompt exceeds total prompt budget")
        schema = RESPONSE_SCHEMAS[self._code]
        original_generate = self._client.generate
        contract = (
            ResponseContract.json_schema(
                schema, name=f"sme_{self._code.lower().replace('-', '_')}"
            )
            if get_settings().llm_response_mode == "json_schema"
            else ResponseContract.json_object()
        )
        raw = original_generate(
            self._preamble.rstrip() + "\n\n" + prompt,
            response_contract=contract,
            **kwargs,
        )
        validate(self._code, parse_json_payload(raw))
        return raw


__all__ = [
    "REGISTERED_CODES",
    "is_registered",
    "run_criterion",
]
