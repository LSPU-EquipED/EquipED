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

import json
import logging
from dataclasses import dataclass
from typing import Any

from .bands import ratio_band

logger = logging.getLogger(__name__)

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
            "A-05: %s",
            str(exc)[:200],
        )
        return None

    return compute(
        objectives=objectives,
        curriculum_alignment=alignment,
        curriculum_text=curriculum_text,
    )


__all__ = [
    "CurriculumAlignmentResult",
    "compute",
    "evaluate_against_curriculum",
    "PROMPT",
]
