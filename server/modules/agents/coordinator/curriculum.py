"""Coordinator curriculum alignment scoring and canonical grounding.

Coordinator evaluates learning objective alignment against authoritative
course curriculum content for rubric criterion A-05. Objectives and raw
alignment rows are extracted in a single LLM call via ``extraction.extract``.
This module provides pure, deterministic grounding verification and scoring via
``compute()``: positive alignment claims must be supported by an exact verbatim
substring in the authoritative curriculum text. Claims failing grounding are
demoted to unaddressed with empty evidence. There is no secondary LLM call or
additive fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..sme.bands import ratio_band


def format_roadmap_note(roadmap_context: dict[str, Any] | None) -> str:
    """Render only the bounded, canonical roadmap fields for Coordinator."""
    if not isinstance(roadmap_context, dict):
        return ""
    fields = (
        ("course_code", "Course code"),
        ("course_title", "Title"),
        ("year", "Year"),
        ("semester", "Semester"),
        ("tech_stack", "Tech stack"),
        ("competency_stage", "Competency stage"),
        ("course_status", "Course status"),
    )
    values: list[str] = []
    for key, label in fields:
        value = roadmap_context.get(key)
        if value is None or value == "" or isinstance(value, (dict, list, tuple, set)):
            continue
        text = str(value).strip()
        if text:
            values.append(f"{label}: {text}")
    if not values:
        return ""
    # Keep this advisory insertion compact and bounded independently of source text.
    return "Program roadmap context (advisory): " + "; ".join(values)[:1000]


@dataclass
class CurriculumAlignmentResult:
    score: int
    pct: float | None
    aligned: int
    total_objectives: int
    objectives: list[dict[str, Any]]
    curriculum_alignment: list[dict[str, Any]]
    curriculum_text: str
    grounding_rejected_count: int = 0


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
    if len(valid_ids) != len(objectives):
        raise ValueError("curriculum objectives must have unique ids")
    allowed = {"objective_id", "is_addressed", "evidence"}
    if len(curriculum_alignment) > 100 or any(
        not isinstance(row, dict) or set(row) != allowed for row in curriculum_alignment
    ):
        raise ValueError("invalid curriculum alignment row schema")
    if len({row["objective_id"] for row in curriculum_alignment}) != len(
        curriculum_alignment
    ):
        raise ValueError("duplicate curriculum alignment objective")
    if {row["objective_id"] for row in curriculum_alignment} != valid_ids:
        raise ValueError("alignment rows must match objective ids")

    canonical_rows: list[dict[str, Any]] = []
    grounding_rejected_count = 0
    aligned = 0

    for row in curriculum_alignment:
        obj_id = row["objective_id"]
        is_addressed = row["is_addressed"]
        evidence = row["evidence"]

        if is_addressed:
            stripped = evidence.strip() if isinstance(evidence, str) else ""
            if stripped and stripped in curriculum_text:
                canonical_rows.append(
                    {
                        "objective_id": obj_id,
                        "is_addressed": True,
                        "evidence": stripped,
                    }
                )
                aligned += 1
            else:
                grounding_rejected_count += 1
                canonical_rows.append(
                    {
                        "objective_id": obj_id,
                        "is_addressed": False,
                        "evidence": "",
                    }
                )
        else:
            canonical_rows.append(
                {
                    "objective_id": obj_id,
                    "is_addressed": False,
                    "evidence": "",
                }
            )

    band = ratio_band(aligned, len(objectives), scale="moderate")
    return CurriculumAlignmentResult(
        score=band.band,
        pct=band.pct,
        aligned=aligned,
        total_objectives=len(objectives),
        objectives=objectives,
        curriculum_alignment=canonical_rows,
        curriculum_text=curriculum_text,
        grounding_rejected_count=grounding_rejected_count,
    )


__all__ = [
    "CurriculumAlignmentResult",
    "compute",
    "format_roadmap_note",
]
