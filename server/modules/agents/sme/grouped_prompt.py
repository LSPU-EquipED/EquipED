"""Prompt construction for SME's grouped LLM-scoring calls.

Each criterion's scoring rule text is copied verbatim from
``registry._render()``'s justification templates -- the single source of
truth for the threshold each retired ``compute()`` function used -- so the
LLM is anchored to the same numeric bands, not asked to invent its own scale.
"""

from __future__ import annotations

import json
from typing import Any

from .groups import slice_for_group

_DESCRIPTIONS: dict[str, str] = {
    "A-01": "Students are engaged in transforming what they learn.",
    "A-02": (
        "Teachers can easily assess students' progress by using varied "
        "assessment tools."
    ),
    "A-03": (
        "The material keeps an on-going record of students' progress and "
        "allows the teacher to monitor student performance."
    ),
    "A-04": (
        "Positive, meaningful feedback, and prescriptive guides for "
        "interventions are provided."
    ),
    "A-05": "Objectives are gauged effectively.",
    "OP-01": "Topics are coherent from Unit to Chapter.",
    "OP-02": (
        "Material is interactive in each lesson which makes life-long "
        "learning easier."
    ),
    "OP-03": (
        "Directions are clear and complete enough for students to perform "
        "required tasks."
    ),
    "OP-04": "Paragraphs and sections have clear and accurate information.",
    "OP-05": "Enhancement activities for students are provided.",
}

_SCORING_RULES: dict[str, str] = {
    "A-01": (
        "Score the percentage of tasks that engage higher-order thinking "
        "(apply/analyze/evaluate/create, not just remember/understand) on "
        "the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. "
        "No tasks found -> 1."
    ),
    "A-02": (
        "Count distinct assessment TYPES used (objective test, written, "
        "reflection, performance task, project, oral, self-assessment). "
        "Score: 5+ types -> 4, 3-4 types -> 3, 2 types -> 2, <=1 type -> 1."
    ),
    "A-05": (
        "Score the percentage of stated objectives that are measured by a "
        "real assessment on the moderate scale: 4 if >=80%, 3 if >=50%, "
        "2 if >=20%, else 1. No objectives found -> 1."
    ),
    "OP-02": (
        "Count genuine interactive elements with real task content (not "
        "just a label like 'Activity 1' with no actual task). Score: "
        "4+ elements -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
    "OP-03": (
        "Score the percentage of tasks with clear, complete directions on "
        "the moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "OP-05": (
        "Count genuine enhancement activities beyond the core lesson "
        "content. Score: 3+ activities -> 4, 2 -> 3, 1 -> 2, 0 -> 1."
    ),
    "OP-01": (
        "If there are fewer than 4 topic-to-topic transitions total, score "
        "by issue count instead (a short module with 0 issues is coherent, "
        "not deficient): 0 issues -> 4, 1 -> 3, 2 -> 2, 3+ issues -> 1. "
        "Otherwise (4+ transitions), score the percentage of transitions "
        "that are coherent (each topic logically follows the last) on the "
        "moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. No "
        "topics at all -> 1."
    ),
    "OP-04": (
        "Score the percentage of sections that are clear and internally "
        "consistent (no contradictions or garbled content) on the moderate "
        "scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "A-04": (
        "Count distinct feedback/intervention mechanism TYPES (answer key, "
        "rubric, remediation referral, positive reinforcement). Score: "
        "3-4 types -> 4, 2 types -> 3, 1 type -> 2, 0 types -> 1."
    ),
    "A-03": (
        "Count genuine progress-monitoring mechanisms, spanning up to 4 "
        "types (checkpoint, self-assessment, reflection, cumulative). "
        "Score: 4+ mechanisms -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
}


def build_group_prompt(
    group: str,
    codes: tuple[str, ...],
    titles: dict[str, str],
    full_text: str,
    *,
    prompt_preamble: str | None = None,
) -> str:
    document_text = slice_for_group(group, full_text)
    criteria: dict[str, Any] = {
        code: {
            "title": titles[code],
            "description": _DESCRIPTIONS[code],
            "scoring_rule": _SCORING_RULES[code],
        }
        for code in codes
    }
    instructions = [
        "Return JSON with summary and criterion_scores only.",
        "Return exactly one criterion for each criterion, in this exact order "
        "and with these exact titles: "
        + "; ".join(f"{code} = {titles[code]}" for code in codes),
        "Each criterion score must be between 1 and 4.",
        "Follow each criterion's scoring_rule exactly -- state the count or "
        "percentage you found in the justification so the score is auditable.",
        "Ground all claims in the provided document_text.",
    ]
    payload = {
        "agent": "sme",
        "group": group,
        "document_text": document_text,
        "criteria": criteria,
        "instructions": instructions,
    }
    body = json.dumps(payload, ensure_ascii=False)
    return (
        (prompt_preamble.rstrip() + "\n\n" + body)
        if prompt_preamble
        else body
    )


__all__ = ["build_group_prompt"]
