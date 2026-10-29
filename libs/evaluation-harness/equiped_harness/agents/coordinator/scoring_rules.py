"""Historical adapter 1–3 scoring text retained for seed/replay compatibility.

Current adapter 4 guidance lives in rubric.py and its published database revision.
Applied migrations embed their own immutable copies of these historical rules.
"""

from __future__ import annotations

COORDINATOR_SCORING_RULES: dict[str, str] = {
    "OP-01": (
        "If there are fewer than 4 topic-to-topic transitions total, score "
        "by issue count instead (a short module with 0 issues is coherent, "
        "not deficient): 0 issues -> 4, 1 -> 3, 2 -> 2, 3+ issues -> 1. "
        "Otherwise (4+ transitions), score the percentage of transitions "
        "that are coherent (each topic logically follows the last) on the "
        "moderate scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. No "
        "topics at all -> 1."
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
    "OP-04": (
        "Score the percentage of sections that are clear and internally "
        "consistent (no contradictions or garbled content) on the moderate "
        "scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1."
    ),
    "OP-05": (
        "Count genuine enhancement activities beyond the core lesson "
        "content. Score: 3+ activities -> 4, 2 -> 3, 1 -> 2, 0 -> 1."
    ),
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
    "A-03": (
        "Count genuine progress-monitoring mechanisms, spanning up to 4 "
        "types (checkpoint, self-assessment, reflection, cumulative). "
        "Score: 4+ mechanisms -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1."
    ),
    "A-04": (
        "Count distinct feedback/intervention mechanism TYPES (answer key, "
        "rubric, remediation referral, positive reinforcement). Score: "
        "3-4 types -> 4, 2 types -> 3, 1 type -> 2, 0 types -> 1."
    ),
    "A-05": (
        "Score the percentage of the SLM's stated objectives that are "
        "addressed by the confirmed course curriculum on the moderate "
        "scale: 4 if >=80%, 3 if >=50%, 2 if >=20%, else 1. An objective "
        "counts as addressed only when a verbatim span of the CURRICULUM "
        "CONTEXT supports it. No objectives found, or none addressed by the "
        "curriculum -> 1."
    ),
}

__all__ = ["COORDINATOR_SCORING_RULES"]
