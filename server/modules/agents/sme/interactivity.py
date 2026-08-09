"""OP-02 Interactivity: how much genuine student interaction does the SLM offer?

Rubric intent: "Material is interactive in each lesson which makes life-long
learning easier." We measure this as an INTERACTION COUNT (Pattern B): count the
genuine interactive elements and band by amount. We deliberately do NOT divide by
"lessons" or "topics" -- most SLMs have one unlabeled lesson, and LLM topic-
splitting is unstable, so a topic denominator would wobble the score. A raw count
of real interactive elements needs no fragile denominator.

Band: 0 elements -> 1, 1 -> 2, 2-3 -> 3, 4+ -> 4.

An element counts ONLY IF it has actual task content (a bare "Activity 1" title is
not enough) -- the same real-content rule used by A-05 (see docs/sme-scoring-
basis.md sections 5-6).

Shape mirrors objective_alignment.py: a pure ``compute`` (facts -> band) plus a
thin ``evaluate`` wrapper the CLI uses to run it standalone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .bands import count_band

# 4+ elements -> 4, 2-3 -> 3, 1 -> 2, 0 -> 1.
THRESHOLDS: tuple[tuple[int, int], ...] = ((4, 4), (2, 3), (1, 2))

# The SLM template's fixed section headers where activities/assessments live.
# These are template section NAMES (not content vocabulary), so anchoring on
# them to locate the activity region is stable across SLMs.
ACTIVITY_MARKERS: tuple[str, ...] = (
    "learning strategies",
    "student learning",
    "strategies",
    "activity",
    "activities",
    "assessment",
    "performance task",
    "exercise",
)

PROMPT = """You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

List every GENUINE interactive element in the module: any activity, task,
exercise, prompt, or question that requires the student to actively DO or respond
to something (write, solve, reflect, apply, discuss, self-check, etc.).

STRICT rules:
- Count an element ONLY IF it has actual task CONTENT the student acts on. A bare
  title or heading with no task under it (e.g. just "Activity 1" or "Final Quiz")
  does NOT count.
- List each DISTINCT element once. Do not repeat the same element.
- Passive material the student only reads (explanations, examples) does NOT count.

For each element, put a short label in "text" and the exact triggering content in
"evidence". If you cannot quote real task content for it, do not list it.

Return ONLY valid JSON in exactly this shape:
{{
  "interactive_elements": [
    {{"id": 1, "text": "short label", "evidence": "exact quote of the task"}}
  ]
}}

SLM CONTENT:
{content}
"""


def slice_for_interactivity(text: str, *, head: int = 2000, body: int = 9000) -> str:
    """Keep the head (for context) plus the activity/assessment region where
    interactive elements live. Drops the front matter to stay within the token
    budget. Anchors on the SLM template's fixed section headers.
    """
    if len(text) <= head + body:
        return text
    head_part = text[:head]

    lower = text.lower()
    start: int | None = None
    for marker in ACTIVITY_MARKERS:
        idx = lower.find(marker, head)
        if idx != -1 and (start is None or idx < start):
            start = idx
    if start is None:
        start = head
    body_part = text[start : start + body]
    return head_part + "\n\n[...front matter omitted...]\n\n" + body_part


@dataclass
class InteractivityResult:
    score: int
    count: int
    elements: list[dict[str, Any]]
    genuine: list[dict[str, Any]]


def compute(elements: list[dict[str, Any]]) -> InteractivityResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    Counts DISTINCT elements that carry real content (non-empty evidence),
    deduped by label. The evidence requirement enforces the "must have real task
    content, not just a title" rule; the dedupe guards against the same element
    being listed twice (the class of bug that inflated A-05 to 10/3).
    """
    seen: set[str] = set()
    genuine: list[dict[str, Any]] = []
    for element in elements:
        evidence = str(element.get("evidence", "")).strip()
        if not evidence:  # bare title / no real content -> does not count
            continue
        key = str(element.get("text", "")).strip().lower() or evidence.lower()
        if key in seen:
            continue
        seen.add(key)
        genuine.append(element)

    count = len(genuine)
    score = count_band(count, THRESHOLDS)
    return InteractivityResult(
        score=score,
        count=count,
        elements=elements,
        genuine=genuine,
    )


def evaluate(client: Any, text: str) -> InteractivityResult:
    """Thin wrapper: fetch facts from the LLM, then compute the band.

    Used by the CLI to run OP-02 standalone. At integration the facts come from
    a shared/grouped call instead, but ``compute`` stays the same.
    """
    content = slice_for_interactivity(text)
    raw = client.generate(
        PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1200,
    )
    data = json.loads(raw)
    return compute(list(data.get("interactive_elements", [])))


__all__ = [
    "InteractivityResult",
    "compute",
    "evaluate",
    "slice_for_interactivity",
    "THRESHOLDS",
    "PROMPT",
]
