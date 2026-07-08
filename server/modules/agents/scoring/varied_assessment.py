"""A-02 Varied Assessment Tools: does the SLM use more than one kind of
assessment to gauge student progress?

Rubric intent: "Teachers can easily assess students' progress by using varied
assessment tools." We measure this as a CHECKLIST COUNT (Pattern B, like
OP-02/OP-05): count how many DISTINCT assessment TYPES appear, not how many
assessments exist -- five multiple-choice quizzes are one type, not five.

    band: 0-1 types -> 1, 2 -> 2, 3-4 -> 3, 5+ -> 4

The LLM only enumerates assessments and classifies each into exactly one type
from a FIXED, code-owned taxonomy (see ASSESSMENT_TYPES below) -- the same
"boundary lives in code, not the prompt" approach as A-01's Bloom levels. This
is a deliberate choice over letting the LLM invent free-text type labels: free
labels drift ("quiz" vs "short quiz") and can inflate the count artificially,
which is exactly the instability this project has been fixing criterion by
criterion. A type counts only if a real assessment can be quoted as evidence --
a bare title like "Final Exam" with no content is not enough (same real-content
rule as A-05 / OP-02 / OP-03 / OP-05 / A-01, see docs/sme-scoring-basis.md).

Shape mirrors enhancement_activities.py: a pure ``compute`` (facts -> band)
plus a thin ``evaluate`` wrapper the CLI uses to run it standalone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .bands import count_band

# >=5 distinct types -> 4, 3-4 -> 3, 2 -> 2, <=1 -> 1.
THRESHOLDS: tuple[tuple[int, int], ...] = ((5, 4), (3, 3), (2, 2))

# Fixed, code-owned taxonomy. The LLM maps each assessment to exactly one of
# these; unrecognized/free-text labels are dropped (see _normalize_type),
# which keeps the type boundary auditable and resistant to inflation.
ASSESSMENT_TYPES: tuple[str, ...] = (
    "objective_test",  # selected-response: multiple choice, T/F, matching, ID
    "written",  # short-answer, essay, written composition
    "reflection",  # reflection journal, reaction paper
    "performance_task",  # performance task, demonstration, skills exhibition
    "project",  # project, product, portfolio
    "oral",  # oral recitation, presentation, defense
    "self_assessment",  # self-check, peer assessment, rating scale
)

# SLMs put their actual assessments in a dedicated section near the BOTTOM,
# under a strong header (most often "Performance Task(s)"). Same anchors as
# enhancement_activities.SECTION_ANCHORS / learner_transformation -- anchoring
# on the section header (not vocabulary) avoids pulling lecture content in.
SECTION_ANCHORS: tuple[str, ...] = (
    "performance task",
    "performance tasks",
    "learning tasks",
    "enrichment activit",
    "enhancement activit",
    "assessment task",
    "questions for reflection",
)

PROMPT = """You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

List every ASSESSMENT TOOL used to gauge student progress: any quiz, test,
task, or activity whose PURPOSE is to measure or record what the student has
learned (not just practice).

For EACH assessment, classify it into EXACTLY ONE of these seven types:
- "objective_test"    -- selected-response items: multiple choice, true/false,
                         matching, identification
- "written"            -- short-answer or essay questions, written composition
- "reflection"         -- reflection journal, reaction paper, learning log
- "performance_task"   -- performance task, demonstration, skills exhibition
- "project"            -- project, product, portfolio, output requiring
                         extended work
- "oral"               -- oral recitation, presentation, defense, interview
- "self_assessment"    -- self-check, self-rating, peer assessment

STRICT rules:
- Classify by what the assessment actually asks the student to produce, not by
  its title alone.
- You must be able to quote the actual assessment content as evidence. A bare
  title with no content (e.g. just "Final Exam") is NOT sufficient -- still
  list it, but with empty "evidence".
- List each DISTINCT assessment once. Do not repeat the same assessment.
- If an assessment does not clearly fit one of the seven types, do not force
  it -- omit it rather than guessing.

For each assessment put a short label in "text", one of the seven types in
"assessment_type", and the exact assessment text in "evidence".

Return ONLY valid JSON in exactly this shape:
{{
  "assessments": [
    {{"id": 1, "text": "short label", "assessment_type": "objective_test",
      "evidence": "exact assessment text"}}
  ]
}}

SLM CONTENT:
{content}
"""


def slice_for_variety(text: str, *, body: int = 9000) -> str:
    """Read only the assessments section, anchored on its header.

    SLMs place their real assessments near the bottom under a strong header
    (usually "Performance Task(s)"). We find the EARLIEST such header and read
    from there to the end (capped at ``body`` chars). If no header is found,
    fall back to the tail of the document, where assessments live regardless.
    """
    lower = text.lower()

    start: int | None = None
    for anchor in SECTION_ANCHORS:
        idx = lower.find(anchor)
        if idx != -1 and (start is None or idx < start):
            start = idx

    if start is None:
        return text[-body:] if len(text) > body else text
    return text[start : start + body]


def _normalize_type(raw: str) -> str:
    """Map free-text type to one of ASSESSMENT_TYPES, or "" if unrecognized.

    Matches by prefix/equality against the canonical, underscore-joined form so
    the LLM's exact-string output normalizes cleanly. Anything unrecognized
    normalizes to "" and is dropped -- conservative, so a mis-tagged or
    invented type cannot inflate the distinct-type count.
    """
    cleaned = raw.strip().lower().replace(" ", "_").replace("-", "_")
    for kind in ASSESSMENT_TYPES:
        if cleaned == kind or cleaned.startswith(kind):
            return kind
    return ""


@dataclass
class VarietyResult:
    score: int
    count: int
    types: list[str]
    assessments: list[dict[str, Any]]
    genuine: list[dict[str, Any]]


def compute(assessments: list[dict[str, Any]]) -> VarietyResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    Denominator concept here is inverted from the ratio criteria: we count
    DISTINCT TYPES represented among assessments that carry real content (the
    evidence requirement enforces the "must have real content, not just a
    title" rule), not the number of assessment instances. Several instances of
    the same type collapse to one entry in the type set, by design -- five
    quizzes are one type, not five.
    """
    genuine: list[dict[str, Any]] = []
    types: set[str] = set()
    for assessment in assessments:
        evidence = str(assessment.get("evidence", "")).strip()
        if not evidence:  # bare title / no real content -> does not count
            continue
        kind = _normalize_type(str(assessment.get("assessment_type", "")))
        if not kind:  # unrecognized type -> dropped, not guessed
            continue
        genuine.append(assessment)
        types.add(kind)

    count = len(types)
    score = count_band(count, THRESHOLDS)
    return VarietyResult(
        score=score,
        count=count,
        types=sorted(types),
        assessments=assessments,
        genuine=genuine,
    )


def evaluate(client: Any, text: str) -> VarietyResult:
    """Thin wrapper: fetch facts from the LLM, then compute the band.

    Used by the CLI to run A-02 standalone. At integration the facts come from
    a shared/grouped call instead, but ``compute`` stays the same.
    """
    content = slice_for_variety(text)
    raw = client.generate(
        PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1500,
    )
    data = json.loads(raw)
    return compute(list(data.get("assessments", [])))


__all__ = [
    "VarietyResult",
    "compute",
    "evaluate",
    "slice_for_variety",
    "ASSESSMENT_TYPES",
    "THRESHOLDS",
    "PROMPT",
]
