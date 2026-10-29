"""Historical Coordinator prompt shapes used by saved-result validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from equiped_harness.contracts import (
    CountBandConfig,
    CriterionDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.runtime.prompts import AgentPrompt

_EVIDENCE_FOCUS = {
    "OP-01": (
        "Explain how actual topic transitions connect or break the lesson sequence."
    ),
    "OP-02": (
        "Quote an actual student interaction task, not a description of the subject."
    ),
    "OP-03": (
        "Quote actual directions for a student task: what to do and "
        "how. For example, a goal to explain a concept is not an "
        "instruction; a question followed by steps to answer it is."
    ),
    "OP-04": (
        "Explain an observed clear connection or inconsistency between "
        "statements; do not claim external fact verification."
    ),
    "OP-05": (
        "Quote an actual extension or practice activity beyond the "
        "lesson explanation, not a heading alone."
    ),
    "A-01": (
        "Quote an actual apply/analyze/evaluate/create task. A goal "
        "saying students should analyze is not a task. A prompt asking "
        "students to compare examples and justify a choice is a task. "
        "Recall questions alone do not qualify."
    ),
    "A-02": (
        "Identify actual assessment tasks and their distinct types, not"
        " just delivery platforms or lesson goals."
    ),
    "A-03": (
        "Look for an actual checkpoint, self-assessment, reflection "
        "record or cumulative tracker of student performance. A list of"
        " learning objectives is not a progress record. If none is "
        "identified, return absent."
    ),
    "A-04": (
        "Look for actual answer feedback, a marking rubric, remediation"
        " or positive reinforcement for students. Advice about the "
        "lesson subject is not feedback to learners. If none is "
        "identified, return absent."
    ),
}


@dataclass(frozen=True, slots=True)
class _Task:
    task_id: str
    kind: str
    criteria: tuple[CriterionDefinition, ...]
    prompt: AgentPrompt


def _canonical_ordinary_example(config: Any) -> tuple[str, str]:
    """Return the exact one-row example and repair contract for a strategy."""
    if isinstance(config, LlmRubricGuidanceConfig):
        return (
            '{"results":[{"status":"supported","score":3,"evidence_id":"slm-0001"}]}',
            "one row with exactly status, score, and evidence_id",
        )
    if isinstance(config, CountBandConfig):
        return (
            '{"results":[{"status":"supported","instance_ids":["slm-0001"]}]}',
            "one row with exactly status and instance_ids",
        )
    if isinstance(config, RatioBandConfig):
        return (
            '{"results":[{"status":"supported","unit_ids":["slm-0001"],"qualifying_unit_ids":["slm-0001"]}]}',
            "one row with exactly status, unit_ids, and qualifying_unit_ids",
        )
    raise AgentExecutionError("Unsupported current Coordinator strategy")
