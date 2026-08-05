"""SME domain agent."""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any

from .contracts import AgentEvaluationResult, CriterionScore
from .engine_scoring import EngineScoredAgent
from .exceptions import AgentExecutionError

# A criterion at or below this score is surfaced in the improvement summary.
_IMPROVEMENT_THRESHOLD = 2

# Fixed, code-side suggestion per criterion -- keyed by ID (not derived from
# the justification text), so the improvement line reads as actionable
# feedback rather than a bare list of criterion names. One entry per
# ``registry.REGISTERED_CODES``.
_IMPROVEMENT_SUGGESTIONS: dict[str, str] = {
    "A-01": "incorporating more higher-order thinking tasks",
    "A-02": "diversifying the types of assessments used",
    "A-03": "adding more checkpoints or reflection activities",
    "A-04": "providing more varied feedback or intervention mechanisms",
    "A-05": "aligning more assessments directly to the stated objectives",
    "OP-01": "adding clearer transitions between topics",
    "OP-02": "adding more interactive elements with real task content",
    "OP-03": "providing clearer, more complete task directions",
    "OP-04": "reviewing sections for clarity and internal consistency",
    "OP-05": "adding more enrichment activities beyond the core content",
}
_DEFAULT_SUGGESTION = "revisiting this criterion"


def _join_with_and(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _build_improvement_summary(criterion_scores: tuple[CriterionScore, ...]) -> str:
    """Deterministic, code-computed summary written as two sentences: the
    strongest criterion first (positive), then every criterion scoring
    <= 2/4 named with a fixed, code-side suggestion attached (see
    ``_IMPROVEMENT_SUGGESTIONS``) -- no raw scores, counts, or percentages.

    Mirrors Coordinator's positive-then-improve flow and number-free style
    (see ``coordinator._build_llm_alignment_summary``), but stays fully
    deterministic -- no LLM call, consistent with SME being purely
    engine-scored.
    """
    if not criterion_scores:
        return ""

    strongest = max(criterion_scores, key=lambda c: c.score)
    positive = f"{strongest.criterion_title} is the strongest area."

    weak = sorted(
        (c for c in criterion_scores if c.score <= _IMPROVEMENT_THRESHOLD),
        key=lambda c: c.score,
    )
    if weak:
        titles = _join_with_and([c.criterion_title for c in weak])
        verb = "needs" if len(weak) == 1 else "need"
        suggestions = _join_with_and(
            [
                _IMPROVEMENT_SUGGESTIONS.get(c.criterion_id, _DEFAULT_SUGGESTION)
                for c in weak
            ]
        )
        improvement = f"{titles} {verb} improvement; consider {suggestions}."
    else:
        improvement = "No areas need improvement."

    return f"{positive} {improvement}"


class SME(EngineScoredAgent):
    agent_name = "sme"
    rubric_source_type = "rubric_sme"
    domain_keywords = (
        "accuracy", "content", "knowledge", "concepts", "theory",
        "definitions", "principles", "facts", "understanding", "correct",
    )

    def run(
        self,
        *,
        evaluation_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_infos: list[dict[str, Any]],
        context_text: str | None = None,
        prompt_version_id: uuid.UUID | None = None,
        db: Any | None = None,
        llm_client: Any | None = None,
        **kwargs: Any,
    ) -> AgentEvaluationResult:
        """Score every SME criterion with the code-side engine directly.

        SME's rubric maps 1:1 onto ``registry.REGISTERED_CODES`` (all 10
        criteria), so there is no LLM-guesses-everything base call worth
        making first -- the engine's grouped pass is the sole primary
        scorer, with a per-criterion fallback for anything it misses (see
        ``EngineScoredAgent._score_via_engine``). A code that fails both
        raises ``AgentExecutionError``, matching every other agent's
        all-or-nothing failure contract (the Supervisor already handles a
        raised agent by marking it failed and excluding it from synthesis).
        """
        if not chunk_infos:
            raise AgentExecutionError("document chunks are required for evaluation")

        if llm_client is not None:
            self._llm_client = llm_client

        result = self._run_full_engine_scoring(
            evaluation_id=evaluation_id,
            document_id=document_id,
            chunk_infos=chunk_infos,
            context_text=context_text,
            prompt_version_id=prompt_version_id,
            db=db,
        )
        return dataclasses.replace(
            result,
            summary=_build_improvement_summary(result.criterion_scores),
        )


SMEAgent = SME


__all__ = ["SME", "SMEAgent"]
