from __future__ import annotations

import json
import logging
from typing import Any

from server.core.llm import get_llm_model_name

from ..contracts import CriterionScore
from ..exceptions import AgentLLMError
from ..runtime.llm import FallbackAwareClient, error_reference

logger = logging.getLogger(__name__)

def _build_alignment_summary(criterion_scores: tuple[CriterionScore, ...]) -> str:
    """Summarize objective-to-curriculum alignment from Coordinator's own
    A-05 score.

    A-05 is the one criterion Coordinator always computes independently
    (curriculum-grounded when a curriculum is attached, SLM-only otherwise --
    see ``run()``), so it's the only source of Coordinator-specific insight;
    the other 9 scores are reused from SME (see ``merge_with_sme``) and
    would misrepresent Coordinator's own review if summarized here.
    """
    a05 = next((c for c in criterion_scores if c.criterion_id == "A-05"), None)
    if a05 is None:
        return ""
    return f"Objective-curriculum alignment: {a05.justification}"


def _build_llm_alignment_summary(
    criterion_scores: tuple[CriterionScore, ...],
    client: Any,
) -> str:
    """LLM-written Coordinator summary: a positive observation first (which
    may cite ANY strong criterion across the full merged rubric, not just
    A-05), then the single area most in need of improvement -- Coordinator's
    own objective-curriculum alignment (A-05) when it has a real gap,
    otherwise the weakest-scoring criterion elsewhere.

    Requires the FULL merged 10-criterion set to let the positive line draw
    on more than A-05 -- callers with only A-05 available (e.g. Coordinator's
    own ``run()``, before SME's scores are merged in) should not call this;
    use ``_build_alignment_summary`` instead and let the merge step upgrade
    it later. The LLM only rephrases facts already computed by the engine
    (scores and their justifications); it is not asked to score anything.
    Falls back to the deterministic ``_build_alignment_summary`` text (A-05
    only) if the call fails, the response isn't valid JSON, or no client is
    available -- a summary-generation failure must never take down
    Coordinator's result.
    """
    fallback = _build_alignment_summary(criterion_scores)
    a05 = next((c for c in criterion_scores if c.criterion_id == "A-05"), None)
    if a05 is None or client is None:
        return fallback

    others = sorted(
        (c for c in criterion_scores if c.criterion_id != "A-05"),
        key=lambda c: -c.score,
    )
    others_context = [
        {"criterion": c.criterion_title, "score": c.score, "note": c.justification}
        for c in others
    ]

    prompt = json.dumps(
        {
            "task": "Write a 2-sentence Program Coordinator review comment "
            "using ONLY these facts -- invent nothing.",
            "your_criterion": {
                "name": "Objective-Curriculum Alignment",
                "score": a05.score,
                "note": a05.justification,
            },
            "other_rubric_context": others_context,
            "score_scale": "1=Poor, 4=Very Satisfactory",
            "structure": "Sentence 1 = positive (your_criterion or the "
            "best entry in other_rubric_context). Sentence 2 = area to "
            "improve (your_criterion if it has a real gap, else the "
            "lowest-scoring entry in other_rubric_context).",
            "style": "Terse, qualitative, no raw numbers/percentages, no "
            "filler openers. Example: 'Objectives are well-aligned with "
            "the curriculum. Assessment types are limited; more variety "
            "would strengthen coverage.'",
            "instructions": 'Return ONLY valid JSON: {"summary": "..."}.',
        },
        ensure_ascii=False,
    )

    adapter = (
        client
        if isinstance(client, FallbackAwareClient)
        else FallbackAwareClient(
            client,
            "coordinator",
            requested_model=(
                getattr(client, "model", None) or get_llm_model_name()
            ),
        )
    )
    try:
        raw = adapter.generate(prompt, temperature=0.3, max_new_tokens=220)
        payload = raw.strip()
        if payload.startswith("```"):
            payload = payload.strip("`")
            if payload.lower().startswith("json"):
                payload = payload[4:]
        parsed = json.loads(payload.strip())
        summary = parsed.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    except Exception as exc:
        logger.warning(
            "Coordinator LLM summary generation failed, using deterministic "
            "fallback (category=%s, reference=%s)",
            AgentLLMError.__name__, error_reference(exc),
        )
    return fallback


__all__ = ["_build_alignment_summary", "_build_llm_alignment_summary"]
