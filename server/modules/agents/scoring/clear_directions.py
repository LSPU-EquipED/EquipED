"""OP-03 Clear Directions: can students actually follow the task instructions?

Rubric intent: "Directions are clear and complete enough for students to perform
required tasks." We measure this as a COVERAGE RATIO (like A-05): of the tasks the
student is asked to perform, how many carry clear, complete directions?

    clear_directions_ratio = tasks_with_clear_directions / total_tasks

mapped on the moderate scale (>=80% -> 4, >=50% -> 3, >=20% -> 2, else 1). No task
at all -> 1 by the empty rule: if the module asks the student to do nothing, it
cannot demonstrate clear directions.

The LLM only enumerates the tasks and judges per task whether the directions are
clear; the band is computed in code. A task counts as "clear" ONLY IF the actual
direction text can be quoted -- a bare title like "Activity 1" with no instructions
under it is exactly the deficiency this criterion penalizes (same real-content rule
as A-05 / OP-02, see docs/sme-scoring-basis.md).

Shape mirrors interactivity.py / objective_alignment.py: a pure ``compute`` (facts
-> band) plus a thin ``evaluate`` wrapper the CLI uses to run it standalone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .bands import ratio_band

# The SLM template's fixed section headers where tasks/activities (and thus their
# directions) live. Same anchors OP-02 uses -- both read the "activities" region.
TASK_MARKERS: tuple[str, ...] = (
    "learning strategies",
    "student learning",
    "strategies",
    "activity",
    "activities",
    "assessment",
    "performance task",
    "exercise",
    "directions",
    "instructions",
)

PROMPT = """You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

List every TASK the student is asked to perform: any activity, exercise, quiz,
performance task, or prompt that requires the student to DO something.

For EACH task, judge whether its DIRECTIONS are clear and complete, using this
STRICT rule:
- Directions are "clear" ONLY IF the text tells the student what to do well enough
  to actually perform the task (what to do, and where relevant how or what output
  is expected). You must be able to quote the actual direction text.
- A bare task TITLE with no instructions under it (e.g. just "Activity 1") is NOT
  clear -- set has_clear_directions = false.
- Vague or incomplete instructions the student could not follow -> false.
- If unsure, set has_clear_directions = false.

For each task put a short label in "text", the exact instruction text in
"directions", and the true/false judgment in "has_clear_directions". If a task has
no quotable directions, still list it with empty "directions" and false.

Return ONLY valid JSON in exactly this shape:
{{
  "tasks": [
    {{"id": 1, "text": "short label", "directions": "exact instruction quote",
      "has_clear_directions": true}}
  ]
}}

SLM CONTENT:
{content}
"""


def slice_for_directions(text: str, *, head: int = 2000, body: int = 9000) -> str:
    """Keep the head (for context) plus the task/activity region where directions
    live. Drops the front matter to stay within the token budget. Anchors on the
    SLM template's fixed section headers.
    """
    if len(text) <= head + body:
        return text
    head_part = text[:head]

    lower = text.lower()
    start: int | None = None
    for marker in TASK_MARKERS:
        idx = lower.find(marker, head)
        if idx != -1 and (start is None or idx < start):
            start = idx
    if start is None:
        start = head
    body_part = text[start : start + body]
    return head_part + "\n\n[...front matter omitted...]\n\n" + body_part


@dataclass
class DirectionsResult:
    score: int
    pct: float | None
    clear: int
    total: int
    tasks: list[dict[str, Any]]
    clear_tasks: list[dict[str, Any]]


def compute(tasks: list[dict[str, Any]]) -> DirectionsResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    Denominator = DISTINCT tasks the student must perform. Numerator = tasks the
    LLM judged clear AND that carry a quotable direction (the evidence requirement
    enforces the "must have real instructions, not just a title" rule). Dedupe by
    label guards against the same task being listed twice (the class of bug that
    inflated A-05 to 10/3).
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for task in tasks:
        label = str(task.get("text", "")).strip().lower()
        key = label or str(task.get("directions", "")).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(task)

    clear_tasks = [
        t
        for t in unique
        if t.get("has_clear_directions") and str(t.get("directions", "")).strip()
    ]

    band = ratio_band(len(clear_tasks), len(unique), scale="moderate")
    return DirectionsResult(
        score=band.band,
        pct=band.pct,
        clear=len(clear_tasks),
        total=len(unique),
        tasks=unique,
        clear_tasks=clear_tasks,
    )


def evaluate(client: Any, text: str) -> DirectionsResult:
    """Thin wrapper: fetch facts from the LLM, then compute the band.

    Used by the CLI to run OP-03 standalone. At integration the facts come from a
    shared/grouped call instead, but ``compute`` stays the same.
    """
    content = slice_for_directions(text)
    raw = client.generate(
        PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1500,
    )
    data = json.loads(raw)
    return compute(list(data.get("tasks", [])))


__all__ = [
    "DirectionsResult",
    "compute",
    "evaluate",
    "slice_for_directions",
    "PROMPT",
]
