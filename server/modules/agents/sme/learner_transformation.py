"""A-01 Learner Transformation: are students pushed to DO something with what
they learn, not just recall it?

Rubric intent: "Students are engaged in transforming what they learn." We
measure this as a COVERAGE RATIO (like OP-03 / A-05): of the tasks the student
is asked to perform, how many require HIGHER-ORDER thinking (Bloom's apply /
analyze / evaluate / create) rather than just remembering or understanding?

    higher_order_ratio = higher_order_tasks / total_tasks

mapped on the moderate scale (>=80% -> 4, >=50% -> 3, >=20% -> 2, else 1). No
task at all -> 1 by the empty rule: if the module asks the student to do
nothing, it cannot demonstrate transformation.

The LLM only enumerates the tasks and tags each with its Bloom cognitive level;
code decides which levels count as "higher-order" (see HIGHER_ORDER below) and
computes the band. Keeping that boundary in code -- not the prompt -- makes it
auditable and changeable without touching the LLM call. A task counts as
higher-order ONLY IF the actual task text can be quoted -- a bare title like
"Activity 1" with no content under it is not evidence of transformation (same
real-content rule as A-05 / OP-02 / OP-03, see
openspec/specs/sme-engine-scoring/spec.md).

Why ACTIVITIES and not OBJECTIVES: the rubric says students must be "engaged in
transforming" -- engagement is something a student DOES, and that happens in the
tasks, not in a stated objective (a promise of intent). Grading the objectives'
Bloom verbs instead would (a) duplicate A-05's input (objective_alignment.py
already reads the objectives) and (b) miss the exact gap this criterion exists to
catch: a module that *promises* higher-order objectives but only delivers recall
worksheets.

Where the tasks live: per openspec/specs/sme-engine-scoring/spec.md, SLM tasks are
concentrated near the BOTTOM of the PDF under a strong header (usually
"Performance Task(s)"), not spread through the lecture body. The input slice
therefore anchors on that section HEADER and reads to the end -- NOT on activity
vocabulary ("activity", "exercise", "assessment", ...), because those words also
appear in the lecture body and would feed the LLM lesson content that then gets
mislabeled as tasks. Same rule and same bug class as OP-05 (see
enhancement_activities.py / slice_for_enhancement).

Shape mirrors clear_directions.py: a pure ``compute`` (facts -> band) plus a
thin ``evaluate`` wrapper the CLI uses to run it standalone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..runtime.llm import parse_json_payload
from .bands import ratio_band

# Bloom's cognitive levels that count as "transformation" -- the student must
# DO something with the material, not just recall or restate it.
HIGHER_ORDER: frozenset[str] = frozenset({"apply", "analyze", "evaluate", "create"})
# The remaining recognized levels (remember, understand) are lower-order and do
# not count toward the numerator; anything unrecognized is treated as
# lower-order too (conservative -- see _normalize_level).
KNOWN_LEVELS: tuple[str, ...] = (
    "remember",
    "understand",
    "apply",
    "analyze",
    "evaluate",
    "create",
)

# SLMs put their actual tasks in a dedicated section near the BOTTOM, under a
# strong header (most often "Performance Task(s)"). We anchor on that header and
# read from there to the end, so the LLM sees the tasks region -- NOT the lecture
# body above it (which was causing content to be mislabeled as activities on
# OP-05 before this same fix). Ordered by precision: the earliest strong header
# wins. Same anchors as enhancement_activities.SECTION_ANCHORS.
SECTION_ANCHORS: tuple[str, ...] = (
    "performance task",
    "performance tasks",
    "learning tasks",
    "enrichment activit",  # matches "activity"/"activities"
    "enhancement activit",
    "assessment task",
    "questions for reflection",
)

PROMPT = """You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

List every TASK the student is asked to perform: any activity, exercise, quiz,
performance task, or prompt that requires the student to DO something.

For EACH task, classify its Bloom's Taxonomy cognitive level based on what the
student must actually DO, using exactly one of these six canonical category names:
- "remember"   -- recall facts, terms, definitions (e.g. list, define, name)
- "understand" -- explain or summarize in their own words (e.g. describe, explain)
- "apply"      -- use a concept in a new situation (e.g. solve, demonstrate, use)
- "analyze"    -- break down, compare, find relationships (e.g. compare, differentiate)
- "evaluate"   -- judge, critique, justify a position (e.g. critique, defend, assess)
- "create"     -- produce something new (e.g. design, build, compose, propose)

IMPORTANT: You MUST return the canonical category name ("remember", "understand",
"apply", "analyze", "evaluate", or "create"), NOT the example action verb (for
example, if the task is to "compare", return "analyze"; if to "explain", return
"understand"; if to "justify", return "evaluate"; if to "list", return "remember").

STRICT rules:
- Classify by what the student must actually DO, not by the topic's difficulty.
- You must quote a minimal evidence quote (the exact instruction or task sentence)
  in "evidence". A bare task TITLE with no content under it (e.g. just "Activity 1")
  is NOT evidence -- still list it, but with empty "evidence".
- If you are unsure between two levels, pick the LOWER one.
- List each DISTINCT task once. Do not repeat the same task.

For each task put a short label in "text", the canonical Bloom level in
"bloom_level", and the minimal evidence quote in "evidence".

Return ONLY valid JSON in exactly this shape:
{{
  "tasks": [
    {{"id": 1, "text": "short label", "bloom_level": "apply",
      "evidence": "exact task text"}}
  ]
}}

SLM CONTENT:
{content}
"""


def slice_for_transformation(text: str, *, body: int = 9000) -> str:
    """Read only the tasks section, anchored on its header.

    SLMs place their real tasks near the bottom under a strong header (usually
    "Performance Task(s)"). We find the EARLIEST such header and read from there
    to the end (capped at ``body`` chars). Everything above -- objectives, the
    lecture body -- is dropped, because that content was being mislabeled as
    tasks. If no header is found, fall back to the tail of the document, where
    tasks live regardless.
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


BLOOM_ALIASES: dict[str, str] = {
    "list": "remember",
    "explain": "understand",
    "compare": "analyze",
    "justify": "evaluate",
}


def _normalize_level(raw: str) -> str:
    """Map free-text Bloom level to one of KNOWN_LEVELS, or "" if unrecognized.

    Matches by prefix for canonical levels (e.g. "analyzing" -> "analyze").
    Also maps exact observed aliases after trim/casefold: list -> remember,
    explain -> understand, compare -> analyze, justify -> evaluate.
    Unrecognized text normalizes to "" and is treated as lower-order --
    conservative, per the "if unsure, pick the lower one" prompt rule.
    """
    cleaned = raw.strip().lower()
    for level in KNOWN_LEVELS:
        if cleaned.startswith(level):
            return level
    return BLOOM_ALIASES.get(cleaned, "")


@dataclass
class TransformationResult:
    score: int
    pct: float | None
    higher_order: int
    total: int
    tasks: list[dict[str, Any]]
    higher_order_tasks: list[dict[str, Any]]


def compute(tasks: list[dict[str, Any]]) -> TransformationResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    Denominator = DISTINCT tasks the student must perform. Numerator = tasks
    whose Bloom level is higher-order AND that carry a quotable evidence (the
    real-content rule). Dedupe by label guards against the same task being
    listed twice (the class of bug that inflated A-05 to 10/3).
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for task in tasks:
        label = str(task.get("text", "")).strip().lower()
        key = label or str(task.get("evidence", "")).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(task)

    higher_order_tasks = [
        t
        for t in unique
        if _normalize_level(str(t.get("bloom_level", ""))) in HIGHER_ORDER
        and str(t.get("evidence", "")).strip()
    ]

    band = ratio_band(len(higher_order_tasks), len(unique), scale="moderate")
    return TransformationResult(
        score=band.band,
        pct=band.pct,
        higher_order=len(higher_order_tasks),
        total=len(unique),
        tasks=unique,
        higher_order_tasks=higher_order_tasks,
    )


def evaluate(client: Any, text: str) -> TransformationResult:
    """Thin wrapper: fetch facts from the LLM, then compute the band.

    Used by the CLI to run A-01 standalone. At integration the facts come from
    a shared/grouped call instead, but ``compute`` stays the same.
    """
    content = slice_for_transformation(text)
    raw = client.generate(
        PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1500,
    )
    data = parse_json_payload(raw)
    return compute(list(data.get("tasks", [])))


__all__ = [
    "TransformationResult",
    "compute",
    "evaluate",
    "slice_for_transformation",
    "HIGHER_ORDER",
    "KNOWN_LEVELS",
    "PROMPT",
]
