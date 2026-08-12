"""Registry of code-side scored SME criteria.

Single source of truth for "which criteria use the engine." Both the CLI
(server/scripts/score_criterion.py) and the SME agent read from here, so a
criterion is migrated in exactly one place. ``run_criterion`` runs a registered
criterion (its own per-criterion LLM call) and returns the pieces the agent
needs to build a ``CriterionScore``: the 1-4 band, a human-readable
justification, and the evidence quotes.

``run_grouped`` is the skeleton-extraction alternative: it runs 6 shared
basket calls (see skeleton.py) instead of one call per criterion, then routes
each basket's facts into the SAME ``compute()`` functions ``run_criterion``
uses -- only the fact *source* changes. Both paths share ``_render`` so the
justification/evidence text is identical either way.

Scoped to SME only. The other agents (Coordinator/GAD/ITSO) are untouched.
"""

from __future__ import annotations

import logging
from typing import Any

from ....core.config import get_settings
from ....core.llm import ResponseContract
from ..runtime.llm import error_reference
from . import (
    accurate_sections,
    clear_directions,
    enhancement_activities,
    extraction,
    interactivity,
    learner_transformation,
    objective_alignment,
    prescriptive_feedback,
    progress_monitoring,
    topic_coherence,
    varied_assessment,
)
from .criterion_contracts import RESPONSE_SCHEMAS, validate

logger = logging.getLogger(__name__)

# Criteria fed from each basket in the grouped/skeleton path. See skeleton.py
# for why monitoring (A3) / enhancement (A4) / sections (B2) each got their
# own dedicated call: bundled with other categories, they came back empty on
# a real-SLM parity test even though the oracle found real content.
_BASKET_A1_CODES: frozenset[str] = frozenset({"A-02", "A-05"})
_BASKET_A2_CODES: frozenset[str] = frozenset({"A-01", "OP-02", "OP-03"})
_BASKET_A3_CODES: frozenset[str] = frozenset({"A-03"})
_BASKET_A4_CODES: frozenset[str] = frozenset({"OP-05"})
_BASKET_B1_CODES: frozenset[str] = frozenset({"OP-01", "A-04"})
_BASKET_B2_CODES: frozenset[str] = frozenset({"OP-04"})

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

    Shared by both ``run_criterion`` (per-criterion call) and ``run_grouped``
    (shared basket call) -- the result objects are identical either way, so the
    rendered text is identical too, regardless of where the facts came from.
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
        import json

        validate(self._code, json.loads(raw))
        return raw


def _compute_basket_a1(criterion_code: str, basket: dict[str, Any]) -> Any:
    """Run one Basket-A1 (assessment-centric) criterion's ``compute()``.

    The same ``assessments`` list feeds both A-02 (types) and A-05 (alignment
    target list) -- each ``compute()`` only reads the keys it needs.
    """
    if criterion_code == "A-05":
        return objective_alignment.compute(
            objectives=list(basket.get("objectives", [])),
            assessments=list(basket.get("assessments", [])),
            alignment=list(basket.get("alignment", [])),
        )
    if criterion_code == "A-02":
        return varied_assessment.compute(list(basket.get("assessments", [])))
    raise KeyError(f"{criterion_code!r} is not a Basket-A1 criterion")


def _compute_basket_a2(criterion_code: str, basket: dict[str, Any]) -> Any:
    """Run one Basket-A2 (task-centric) criterion's ``compute()``.

    The same ``tasks`` list feeds A-01 (bloom_level), OP-02 (evidence-based
    interactive count), and OP-03 (directions) -- each ``compute()`` only reads
    the keys it needs and ignores the rest, so one enumeration serves all
    three. Monitoring/enhancement used to be bundled here too, but a real-SLM
    parity test showed both coming back empty even when real content existed
    -- they now get their own single-purpose baskets (A3, A4).
    """
    if criterion_code == "A-01":
        return learner_transformation.compute(list(basket.get("tasks", [])))
    if criterion_code == "OP-02":
        return interactivity.compute(list(basket.get("tasks", [])))
    if criterion_code == "OP-03":
        return clear_directions.compute(list(basket.get("tasks", [])))
    raise KeyError(f"{criterion_code!r} is not a Basket-A2 criterion")


def _compute_basket_a3(criterion_code: str, basket: dict[str, Any]) -> Any:
    if criterion_code == "A-03":
        return progress_monitoring.compute(
            list(basket.get("monitoring_mechanisms", []))
        )
    raise KeyError(f"{criterion_code!r} is not a Basket-A3 criterion")


def _compute_basket_a4(criterion_code: str, basket: dict[str, Any]) -> Any:
    if criterion_code == "OP-05":
        return enhancement_activities.compute(
            list(basket.get("enhancement_activities", []))
        )
    raise KeyError(f"{criterion_code!r} is not a Basket-A4 criterion")


def _compute_basket_b1(criterion_code: str, basket: dict[str, Any]) -> Any:
    if criterion_code == "OP-01":
        return topic_coherence.compute(
            topics=list(basket.get("topics", [])),
            transitions=list(basket.get("transitions", [])),
        )
    if criterion_code == "A-04":
        return prescriptive_feedback.compute(
            list(basket.get("feedback_mechanisms", []))
        )
    raise KeyError(f"{criterion_code!r} is not a Basket-B1 criterion")


def _compute_basket_b2(criterion_code: str, basket: dict[str, Any]) -> Any:
    if criterion_code == "OP-04":
        return accurate_sections.compute(list(basket.get("sections", [])))
    raise KeyError(f"{criterion_code!r} is not a Basket-B2 criterion")


_BASKETS: tuple[tuple[str, frozenset[str], Any, Any], ...] = (
    ("A1", _BASKET_A1_CODES, extraction.extract_basket_a1, _compute_basket_a1),
    ("A2", _BASKET_A2_CODES, extraction.extract_basket_a2, _compute_basket_a2),
    ("A3", _BASKET_A3_CODES, extraction.extract_basket_a3, _compute_basket_a3),
    ("A4", _BASKET_A4_CODES, extraction.extract_basket_a4, _compute_basket_a4),
    ("B1", _BASKET_B1_CODES, extraction.extract_basket_b1, _compute_basket_b1),
    ("B2", _BASKET_B2_CODES, extraction.extract_basket_b2, _compute_basket_b2),
)


def run_grouped(
    client: Any,
    text: str,
    *,
    raw_baskets_out: dict[str, dict[str, Any]] | None = None,
    basket_extract_kwargs: dict[str, dict[str, Any]] | None = None,
    prompt_preamble: str | None = None,
) -> dict[str, tuple[int, str, tuple[str, ...]]]:
    """Score every registered criterion from 6 shared basket calls instead of
    one call per criterion (see skeleton.py).

    ``raw_baskets_out``, if given, is populated as a side effect with each
    successfully-extracted basket's raw dict, keyed by basket name (e.g.
    ``"A1"`` -> ``{"objectives": [...], "assessments": [...], ...}``). This
    lets a caller reuse already-extracted facts (Coordinator's curriculum
    comparison reuses A1's ``objectives``) without a second LLM call. Purely
    additive -- callers that don't pass it see no change in behavior.

    ``basket_extract_kwargs``, if given, maps a basket name to extra keyword
    arguments forwarded to that basket's ``extract`` function (e.g.
    ``{"A1": {"curriculum_text": "..."}}`` so Coordinator's curriculum
    comparison rides the same A1 call instead of a second LLM round-trip).
    Baskets not named in the mapping get no extra kwargs -- purely additive,
    SME never passes this.

    Earlier, coarser groupings (2 baskets, then 3) were tried and rejected: a
    single merged Basket A (7 criteria in one call) was rejected outright by
    the provider (HTTP 413, request too large); a 3-basket split fit the token
    budget but a real-SLM parity test against the validated per-criterion
    oracle showed monitoring, enhancement, and sections -- all secondary
    categories crammed alongside others in one prompt -- came back completely
    empty despite the oracle finding real content in the same region. Those
    three now get their own dedicated call each. Still 6 calls total instead
    of today's ~10.

    Returns a dict keyed by criterion code -- the SAME ``(score,
    justification, evidence)`` shape ``run_criterion`` returns for that code.
    A code is simply ABSENT from the result if its basket failed to extract or
    its own ``compute()`` raised; callers must treat a missing code as "fall
    back to the per-criterion path or the original LLM score" (see
    ``sme.py._overlay_engine_scores``) -- a basket-level failure must never
    take down criteria that didn't need that basket.
    """
    results: dict[str, tuple[int, str, tuple[str, ...]]] = {}
    budget = get_settings().sme_total_prompt_budget_chars

    for name, codes, extract, compute_fn in _BASKETS:
        extra_kwargs = dict((basket_extract_kwargs or {}).get(name, {}))
        if prompt_preamble or len(text) > get_settings().sme_total_prompt_budget_chars:
            extra_kwargs["prompt_preamble"] = prompt_preamble

        # Preflight the complete managed prompt before transport.  This is
        # intentionally a basket-local gate: other canonical windows must not
        # be shortened merely because one call cannot fit.
        if prompt_preamble:
            content = {
                "A1": extraction.slice_for_basket_a1,
                "A2": extraction.slice_for_basket_a2,
                "A3": extraction.slice_for_basket_a3,
                "A4": extraction.slice_for_basket_a4,
                "B1": extraction.slice_for_basket_b1,
                "B2": extraction.slice_for_basket_b2,
            }[name](text)
            template = getattr(extraction, f"BASKET_{name}_PROMPT")
            complete_prompt = (
                (prompt_preamble.rstrip() + "\n\n") if prompt_preamble else ""
            ) + template.format(content=content)
            if len(complete_prompt) > budget:
                logger.warning(
                    "[SME_GROUPED] basket=%s skipped: complete prompt exceeds budget",
                    name,
                )
                continue

        basket: dict[str, Any] | None
        try:
            basket = extract(client, text, **extra_kwargs)
        except Exception as exc:
            logger.warning(
                "[SME_GROUPED] basket=%s extraction failed: category=%s | reference=%s",
                name,
                type(exc).__name__,
                error_reference(exc),
            )
            basket = None

        if basket is None:
            continue

        if raw_baskets_out is not None:
            raw_baskets_out[name] = basket

        for code in codes:
            try:
                result = compute_fn(code, basket)
                results[code] = _render(code, result)
            except Exception as exc:
                logger.warning(
                    "[SME_GROUPED] criterion=%s failed from basket %s: category=%s | "
                    "reference=%s",
                    code,
                    name,
                    type(exc).__name__,
                    error_reference(exc),
                )

    return results


__all__ = [
    "REGISTERED_CODES",
    "is_registered",
    "run_criterion",
    "run_grouped",
]
