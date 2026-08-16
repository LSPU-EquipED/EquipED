"""OP-05 Enhancement Activities: does the SLM offer activities beyond the core?

Rubric intent: "Enhancement activities for students are provided." We measure this
as a COUNT (Pattern B, like OP-02): count the genuine enhancement activities and
band by amount.

    band: 0 -> 1, 1 -> 2, 2 -> 3, 3+ -> 4

We deliberately do NOT count against a fixed list of enhancement "types"
(enrichment / extension / real-world / ...). Not every SLM uses that vocabulary, so
a keyword-taxonomy denominator isn't justifiable -- the same lesson OP-02 learned.
A raw count of real enhancement activities needs no fragile taxonomy.

An enhancement activity is one offered BEYOND the required core lessons/tasks:
enrichment, extension, extra practice, real-world application, or independent /
further exploration. It counts ONLY IF it has actual content the student acts on (a
bare "Enrichment" heading is not enough) -- the same real-content rule as A-05 /
OP-02 / OP-03 (see openspec/specs/sme-engine-scoring/spec.md).

Shape mirrors interactivity.py: a pure ``compute`` (facts -> band) plus a thin
``evaluate`` wrapper the CLI uses to run it standalone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..runtime.llm import parse_json_payload
from .bands import count_band

# 3+ enhancement activities -> 4, 2 -> 3, 1 -> 2, 0 -> 1.
THRESHOLDS: tuple[tuple[int, int], ...] = ((3, 4), (2, 3), (1, 2))

# SLMs put their actual tasks in a dedicated section near the BOTTOM, under a
# strong header (most often "Performance Task(s)"). We anchor on that header and
# read from there to the end, so the LLM sees the tasks region -- NOT the lecture
# body above it (which was causing content to be mislabeled as activities).
# Ordered by precision: the earliest strong header wins.
SECTION_ANCHORS: tuple[str, ...] = (
    "performance task",
    "performance tasks",
    "learning tasks",
    "enrichment activit",  # matches "activity"/"activities"
    "enhancement activit",
    "assessment task",
)

PROMPT = """You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

List every ENHANCEMENT ACTIVITY: an OPTIONAL task, offered BEYOND the required
core lessons and assessments, that explicitly INSTRUCTS the student to DO
something extra to deepen learning (enrichment, extension, extra practice,
real-world application, independent / further exploration).

What COUNTS as an activity (all must be true):
- It is a direct INSTRUCTION to the student -- it uses a directive telling them to
  act (e.g. "Research...", "Create...", "Interview...", "Try...", "Watch...",
  "Explore...", "Answer...").
- The student has to DO or produce something.
- It is EXTRA / optional -- beyond the required lessons and graded assessments.

What does NOT count (this is the common mistake -- do NOT list these):
- Explanatory or informational CONTENT the student only READS (lesson text,
  definitions, worked examples, background, "did you know" facts, narrative).
- Statements ABOUT real-world relevance that ask the student to do nothing
  (e.g. "This concept is used in engineering.") -- these are content, not tasks.
- Required core lesson tasks or graded assessments (those belong to other
  criteria).
- A bare heading like "Enrichment" with no instruction under it.

For each real activity put a short label in "text" and quote the exact
INSTRUCTION (the words telling the student what to do) in "evidence". If the quote
is not an instruction to the student, do not list it. List each DISTINCT activity
once.

Return ONLY valid JSON in exactly this shape:
{{
  "enhancement_activities": [
    {{"id": 1, "text": "short label", "evidence": "exact instruction to the student"}}
  ]
}}

SLM CONTENT:
{content}
"""


def slice_for_enhancement(text: str, *, body: int = 9000) -> str:
    """Read only the tasks section, anchored on its header.

    SLMs place their real tasks near the bottom under a strong header (usually
    "Performance Task(s)"). We find the EARLIEST such header and read from there
    to the end (capped at ``body`` chars). Everything above -- objectives, the
    lecture body -- is dropped, because that content was being mislabeled as
    activities. If no header is found, fall back to the tail of the document,
    where tasks live regardless.
    """
    lower = text.lower()

    start: int | None = None
    for anchor in SECTION_ANCHORS:
        idx = lower.find(anchor)
        if idx != -1 and (start is None or idx < start):
            start = idx

    if start is None:
        # No recognizable tasks header -> use the tail, where tasks usually sit.
        return text[-body:] if len(text) > body else text
    return text[start : start + body]


@dataclass
class EnhancementResult:
    score: int
    count: int
    elements: list[dict[str, Any]]
    genuine: list[dict[str, Any]]


def compute(elements: list[dict[str, Any]]) -> EnhancementResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    Counts DISTINCT enhancement activities that carry real content (non-empty
    evidence), deduped by label. The evidence requirement enforces the "real
    content, not just a heading" rule; the dedupe guards against the same activity
    being listed twice (the class of bug that inflated A-05 to 10/3).
    """
    seen: set[str] = set()
    genuine: list[dict[str, Any]] = []
    for element in elements:
        evidence = str(element.get("evidence", "")).strip()
        if not evidence:  # bare heading / no real content -> does not count
            continue
        key = str(element.get("text", "")).strip().lower() or evidence.lower()
        if key in seen:
            continue
        seen.add(key)
        genuine.append(element)

    count = len(genuine)
    score = count_band(count, THRESHOLDS)
    return EnhancementResult(
        score=score,
        count=count,
        elements=elements,
        genuine=genuine,
    )


def evaluate(client: Any, text: str) -> EnhancementResult:
    """Thin wrapper: fetch facts from the LLM, then compute the band.

    Used by the CLI to run OP-05 standalone. At integration the facts come from a
    shared/grouped call instead, but ``compute`` stays the same.
    """
    content = slice_for_enhancement(text)
    raw = client.generate(
        PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1200,
    )
    data = parse_json_payload(raw)
    return compute(list(data.get("enhancement_activities", [])))


__all__ = [
    "EnhancementResult",
    "compute",
    "evaluate",
    "slice_for_enhancement",
    "THRESHOLDS",
    "PROMPT",
]
