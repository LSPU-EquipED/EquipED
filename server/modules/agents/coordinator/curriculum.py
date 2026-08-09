"""Coordinator-only extension to A-05: objectives vs. curriculum learning outcomes.

A-05 (Objective Gauging) normally measures whether the SLM's own assessments
measure the SLM's own stated objectives (see ``objective_alignment.py``) --
purely internal to the SLM. This module answers a related but distinct
question, used ONLY by Coordinator: do the SLM's stated objectives align with
what the curriculum prescribes as learning outcomes for this course? Same
"alignment" concept, wider reference set -- not a different criterion.

This does NOT replace ``objective_alignment.py``; SME's path is untouched.
Coordinator runs its normal engine pass first (identical to SME), then -- only
when a curriculum document is attached to the evaluation -- calls
``evaluate_against_curriculum`` here as an additive post-processing step and
replaces just the A-05 entry in its own result.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from dataclasses import dataclass
from typing import Any

from server.modules.embeddings.collections import COL_REFERENCE_ALL
from server.modules.embeddings.retrieval import retrieve_context

from ..contracts import AgentEvaluationResult, CriterionScore
from ..runtime.llm import error_reference
from ..sme.bands import ratio_band

logger = logging.getLogger(__name__)
_CURRICULUM_N_RESULTS = 3

def format_roadmap_note(roadmap_context: dict[str, Any] | None) -> str:
    if not isinstance(roadmap_context, dict) or not roadmap_context:
        return ""
    year = roadmap_context.get("year")
    semester = roadmap_context.get("semester")
    stage = roadmap_context.get("competency_stage")
    tech = roadmap_context.get("tech_stack")
    position = f"Year {year}" if year is not None else ""
    if semester is not None and position:
        position += f" Semester {semester}"
    body = f"{position}{f' with {stage} competency' if stage else ''}"
    if tech:
        body += f"; prescribed tech stack: {tech}"
    return f"Program roadmap places this course at {body}." if body else ""

PROMPT = """You are checking a Self-Paced Learning Module (SLM) against an
official curriculum's course description / learning outcomes.

Your ONLY job is to extract facts. Do NOT assign any score.

Below are the SLM's stated learning OBJECTIVES (already extracted) and the
CURRICULUM CONTENT for the course this SLM belongs to.

For EACH objective, decide whether it is addressed by the curriculum, using
this STRICT rule: the curriculum content must name or clearly imply the same
knowledge/skill as the objective (matching topic and intent). A generic or
unrelated curriculum mention does NOT count. If unsure, mark
is_addressed = false. For every objective you mark true, quote the exact
curriculum text that supports it in "evidence". If you cannot quote real
content, mark false.

Return ONLY valid JSON in exactly this shape:
{{
  "alignment": [
    {{"objective_id": 1, "is_addressed": true, "evidence": "exact quote"}}
  ]
}}

SLM OBJECTIVES:
{objectives}

CURRICULUM CONTENT:
{curriculum_text}
"""


@dataclass
class CurriculumAlignmentResult:
    score: int
    pct: float | None
    aligned: int
    total_objectives: int
    objectives: list[dict[str, Any]]
    curriculum_alignment: list[dict[str, Any]]
    curriculum_text: str


def compute(
    objectives: list[dict[str, Any]],
    curriculum_alignment: list[dict[str, Any]],
    curriculum_text: str,
) -> CurriculumAlignmentResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    Mirrors ``objective_alignment.compute``: counts DISTINCT addressed
    objectives (not alignment rows) against the same moderate-scale ratio
    band, so A-05's scoring math is identical in shape whether the reference
    is the SLM's own assessments (SME/default) or curriculum content
    (Coordinator).
    """
    valid_ids = {o.get("id") for o in objectives}
    addressed_ids = {
        a.get("objective_id")
        for a in curriculum_alignment
        if a.get("is_addressed") and a.get("objective_id") in valid_ids
    }
    aligned = len(addressed_ids)

    band = ratio_band(aligned, len(objectives), scale="moderate")
    return CurriculumAlignmentResult(
        score=band.band,
        pct=band.pct,
        aligned=aligned,
        total_objectives=len(objectives),
        objectives=objectives,
        curriculum_alignment=curriculum_alignment,
        curriculum_text=curriculum_text,
    )


def evaluate_against_curriculum(
    client: Any,
    objectives: list[dict[str, Any]],
    curriculum_text: str,
) -> CurriculumAlignmentResult | None:
    """One LLM call: judge SLM objectives against curriculum content.

    Returns ``None`` on any failure (bad JSON, empty inputs, LLM error) so
    the caller can fall back to the SLM-only A-05 result -- this is an
    additive check, never a hard requirement for Coordinator to produce a
    result.
    """
    if not objectives or not curriculum_text.strip():
        return None

    try:
        raw = client.generate(
            PROMPT.format(
                objectives=json.dumps(objectives),
                curriculum_text=curriculum_text,
            ),
            temperature=0.0,
            max_new_tokens=1200,
        )
        data = json.loads(raw)
        alignment = list(data.get("alignment", []))
    except Exception as exc:
        logger.warning(
            "Curriculum alignment check failed, falling back to SLM-only "
            "A-05 (category=%s, reference=%s)",
            type(exc).__name__, error_reference(exc),
        )
        return None

    return compute(
        objectives=objectives,
        curriculum_alignment=alignment,
        curriculum_text=curriculum_text,
    )


def slm_query_text(agent: Any, document_id: Any, db: Any | None) -> str:
    if db is None:
        return ""
    from server.modules.documents.models import Document
    doc = db.get(Document, document_id)
    if doc is None:
        return ""
    parts = [doc.course_code, doc.course_title or doc.title]
    return " ".join(p for p in parts if p).strip()


def retrieve_curriculum_text(query_text: str, curriculum_id: Any) -> str:
    chunks = retrieve_context(
        query_text, COL_REFERENCE_ALL, n_results=_CURRICULUM_N_RESULTS,
        document_id_filter=str(curriculum_id),
    )
    return "\n\n".join(c.text for c in chunks)


def prepare_curriculum_text(
    agent: Any, document_id: Any, curriculum_id: Any, db: Any | None
) -> str:
    query_text = slm_query_text(agent, document_id, db)
    return retrieve_curriculum_text(query_text, curriculum_id) if query_text else ""


def apply_curriculum_alignment(
    result: AgentEvaluationResult,
    raw_baskets: dict[str, dict[str, Any]],
    curriculum_text: str,
) -> AgentEvaluationResult:
    basket_a1 = raw_baskets.get("A1", {})
    objectives = list(basket_a1.get("objectives", []))
    rows = list(basket_a1.get("curriculum_alignment", []))
    if not objectives or not rows:
        return result
    aligned = compute(objectives, rows, curriculum_text)
    original_title = next(
        (
            c.criterion_title
            for c in result.criterion_scores
            if c.criterion_id == "A-05"
        ),
        "A-05",
    )
    new_score = CriterionScore(
        criterion_id="A-05", criterion_title=original_title, score=aligned.score,
        justification=(f"Curriculum-grounded (coordinator-only): {aligned.aligned}/"
                       f"{aligned.total_objectives} objective(s) addressed by this "
                       f"course's curriculum content. Score {aligned.score}."),
        chunk_ids=(),
        evidence=tuple(
            str(a.get("evidence", ""))
            for a in aligned.curriculum_alignment
            if a.get("is_addressed") and a.get("evidence")
        ),
    )
    updated_scores = tuple(
        new_score if c.criterion_id == "A-05" else c
        for c in result.criterion_scores
    )
    return dataclasses.replace(
        result,
        criterion_scores=updated_scores,
        subtotal=sum(c.score for c in updated_scores) / len(updated_scores),
    )


__all__ = [
    "CurriculumAlignmentResult",
    "compute",
    "evaluate_against_curriculum",
    "PROMPT",
]
