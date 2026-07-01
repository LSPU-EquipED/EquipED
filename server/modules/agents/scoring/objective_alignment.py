"""A-05 Objective Gauging: do the SLM's assessments measure its objectives?

Measurement type: coverage ratio (aligned objectives / total objectives) on the
moderate scale. The LLM only enumerates and judges per objective; the band is
computed in code. A bare assessment title is NOT sufficient evidence -- when the
actual instruments are absent, alignment cannot be demonstrated and the score is
low by design (see docs/sme-scoring-basis.md sections 6 and 9).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .bands import ratio_band

# Keywords marking where the assessment section tends to begin in an SLM.
ASSESSMENT_MARKERS: tuple[str, ...] = (
    "answer me",
    "try this",
    "assessment",
    "performance task",
    "questions for reflection",
    "rubric",
    "evaluation",
    "activity",
    "quiz",
    "post-test",
    "post test",
)

PROMPT = """You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

1. List every stated LEARNING OBJECTIVE / target (the things the student is
   expected to achieve). Keep each as written, briefly.
2. List every ASSESSMENT, activity, or task that requires a student response
   (quizzes, reflection questions, performance tasks, exercises, etc.).
3. For EACH objective, decide whether it is measured, using this STRICT rule:
   An assessment measures an objective ONLY IF completing that assessment
   requires the student to directly demonstrate the specific knowledge or skill
   named in the objective (match the objective's action verb and topic).
   - A general reflection/essay prompt does NOT count unless it targets that
     objective's specific knowledge.
   - A bare assessment TITLE (e.g. "Final Quiz") is NOT sufficient: you must be
     able to quote the actual assessment CONTENT that measures the objective.
   - If unsure, mark is_measured = false.
   For every objective you mark true, put the exact assessment text in
   "evidence". If you cannot quote real content, mark false.

Return ONLY valid JSON in exactly this shape:
{{
  "objectives": [{{"id": 1, "text": "..."}}],
  "assessments": [{{"id": 1, "text": "..."}}],
  "alignment": [
    {{
      "objective_id": 1, "is_measured": true,
      "assessment_ids": [2], "evidence": "exact quote"
    }}
  ]
}}

SLM CONTENT:
{content}
"""


def slice_for_alignment(text: str, *, head: int = 6000, tail: int = 7000) -> str:
    """Keep only what A-05 needs: objectives (near the top) + the assessment
    section. Drops the lecture body to stay within the token budget.
    """
    if len(text) <= head + tail:
        return text
    objectives_part = text[:head]

    lower = text.lower()
    start: int | None = None
    for marker in ASSESSMENT_MARKERS:
        idx = lower.find(marker, head)
        if idx != -1 and (start is None or idx < start):
            start = idx
    if start is None:
        start = len(text) - tail
    assessment_part = text[start : start + tail]
    return objectives_part + "\n\n[...lecture body omitted...]\n\n" + assessment_part


@dataclass
class AlignmentResult:
    score: int
    pct: float | None
    aligned: int
    total_objectives: int
    total_assessments: int
    objectives: list[dict[str, Any]]
    assessments: list[dict[str, Any]]
    alignment: list[dict[str, Any]]


def compute(
    objectives: list[dict[str, Any]],
    assessments: list[dict[str, Any]],
    alignment: list[dict[str, Any]],
) -> AlignmentResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    This is the half that stays per-criterion. The facts it needs (objectives,
    assessments, per-objective alignment judgments) can be produced by this
    criterion's own call OR merged from a shared skeleton/group call later;
    either way the scoring math is identical. See docs/sme-scoring-basis.md s.11.
    """
    # Count DISTINCT measured objectives, not alignment rows: the LLM may emit
    # several rows per objective (one per matching assessment), which would
    # otherwise inflate the numerator past the objective count (e.g. 10/3).
    valid_ids = {o.get("id") for o in objectives}
    measured_ids = {
        a.get("objective_id")
        for a in alignment
        if a.get("is_measured") and a.get("objective_id") in valid_ids
    }
    aligned = len(measured_ids)

    band = ratio_band(aligned, len(objectives), scale="moderate")
    return AlignmentResult(
        score=band.band,
        pct=band.pct,
        aligned=aligned,
        total_objectives=len(objectives),
        total_assessments=len(assessments),
        objectives=objectives,
        assessments=assessments,
        alignment=alignment,
    )


def evaluate(client: Any, text: str) -> AlignmentResult:
    """Thin wrapper: fetch facts from the LLM, then compute the band.

    Used by the CLI to run A-05 standalone. At integration the facts come from
    a shared/grouped call instead, but ``compute`` stays the same.
    """
    content = slice_for_alignment(text)
    raw = client.generate(
        PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1800,
    )
    data = json.loads(raw)
    return compute(
        objectives=list(data.get("objectives", [])),
        assessments=list(data.get("assessments", [])),
        alignment=list(data.get("alignment", [])),
    )


__all__ = ["AlignmentResult", "compute", "evaluate", "slice_for_alignment", "PROMPT"]
