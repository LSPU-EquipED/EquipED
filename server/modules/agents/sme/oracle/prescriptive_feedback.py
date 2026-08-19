"""A-04 Prescriptive Feedback: does the SLM offer students meaningful feedback
and prescriptive guidance for interventions -- anywhere in the module?

Rubric intent: "Positive, meaningful feedback, and prescriptive guides for
interventions are provided." We measure this as a CHECKLIST COUNT (Pattern B,
like OP-02/OP-05/A-02): count how many DISTINCT feedback MECHANISM TYPES the
module provides, from a fixed, code-owned taxonomy.

    band: 0 -> 1, 1 -> 2, 2 -> 3, 3-4 -> 4

REVISION NOTE (superseding an earlier per-assessment ratio design): the
original version required each individual assessment to carry its OWN quotable
feedback/remediation text. In practice, real SLMs almost never attach feedback
per-assessment, so that ratio collapsed to ~0% on nearly every document and
stopped producing useful signal. This version instead asks whether the module
as a WHOLE offers feedback/intervention mechanisms, regardless of which
assessment (if any) they're attached to.

Deliberately counts DISTINCT TYPES, not instances -- the same choice as A-02,
not A-03. The rubric bundles "positive feedback AND prescriptive guides" as
one requirement, which reads as a call for VARIETY of feedback approaches, not
frequency: five answer keys and nothing else should not outscore one answer key
plus a rubric plus a remediation referral. See
openspec/specs/sme-engine-scoring/spec.md and the a02-a03-types-vs-instances
design note.

The LLM only enumerates feedback mechanisms and classifies each into one of
four fixed, code-owned types (see FEEDBACK_TYPES below) -- same "boundary lives
in code, not the prompt" approach as A-01/A-02/A-03. A mechanism counts only if
real content can be quoted as evidence -- a bare heading with no content is not
enough (same real-content rule as the other criteria).

Unlike the task-based criteria (which anchor on the bottom Performance-Tasks
section), feedback/encouragement can live ANYWHERE in the document -- general
remarks near the front matter, a rubric page, a remediation note separate from
the assessments themselves. So this uses the same whole-document downsampling
as OP-01/OP-04 (see slicing.py) instead of a bottom-only slice, and the prompt
carries the same sampled-gap caveat.

Shape mirrors varied_assessment.py: a pure ``compute`` (facts -> band) plus a
thin ``evaluate`` wrapper the CLI uses to run it standalone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ...runtime.llm import parse_json_payload
from .bands import count_band
from .slicing import GAP_MARKER, downsample

# 3-4 distinct types -> 4, 2 -> 3, 1 -> 2, 0 -> 1.
THRESHOLDS: tuple[tuple[int, int], ...] = ((3, 4), (2, 3), (1, 2))

# Fixed, code-owned taxonomy covering both halves of the rubric ("positive
# feedback" + "prescriptive guides"). The LLM maps each mechanism it finds to
# one of these; unrecognized labels are dropped (see _normalize_type).
FEEDBACK_TYPES: tuple[str, ...] = (
    "answer_key",  # model answers / answer key enabling self-check
    "rubric",  # scoring rubric or descriptors explaining evaluation
    "remediation_referral",  # "if you got X, review/do Y" / corrective activity
    "positive_reinforcement",  # encouraging/motivational language re: performance
)

_BOILERPLATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\ball[- ]rights[- ]reserved\b", re.IGNORECASE),
    re.compile(
        r"(?:\bcopyright\b|©|\(c\))\s*(?:notice|owner|by|publisher|granted|\d{4}|[A-Za-z0-9_\s]{1,30}\b(?:19|20)\d{2}\b)",
        re.IGNORECASE,
    ),
    re.compile(r"\bcopyright\s+notice\b|\bcopyright\s+owner\b", re.IGNORECASE),
    re.compile(r"\bfair[- ]use\b", re.IGNORECASE),
    re.compile(r"\bno\s+part\s+of\s+this\b", re.IGNORECASE),
    re.compile(
        r"\bwithout\s+(?:the\s+)?(?:prior\s+)?(?:written\s+)?permission\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\breproduced\s+or\s+transmitted\b|\breproduction\s+(?:or|and)\s+distribution\b|\bprohibited\s+without\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:under|pursuant\s+to)\s+(?:section|[0-9A-Za-z._-]+|\s+)+?(?:republic\s+act|r\.?a\.?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:under|pursuant\s+to)\s+(?:republic\s+act|r\.?a\.?)\s+(?:section|[0-9A-Za-z._-]+|\s+)+",
        re.IGNORECASE,
    ),
)

_PRAISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:great|good|nice|excellent|fantastic|wonderful|amazing|awesome)\s+(?:job|work|effort|done)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:congratulations|congratulation|congrats|bravo|well\s+done|keep\s+it\s+up|keep\s+up\s+the\s+good\s+work|proud\s+of\s+you)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\byou\s+did\s+(?:wonderfully|well)\b",
        re.IGNORECASE,
    ),
)


def _is_high_confidence_boilerplate(text: str) -> bool:
    return any(pattern.search(text) for pattern in _BOILERPLATE_PATTERNS)


def _has_explicit_praise(text: str) -> bool:
    return any(pattern.search(text) for pattern in _PRAISE_PATTERNS)


PROMPT = f"""You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

NOTE: the content below is SAMPLED from across the whole document -- the
marker "{GAP_MARKER.strip()}" marks a span that was OMITTED to fit the sample.
Do NOT treat a "{GAP_MARKER.strip()}" gap as evidence that feedback is
missing -- only judge what you can actually read.

Identify every FEEDBACK or INTERVENTION mechanism the module provides for
students, ANYWHERE in the visible content -- it does NOT need to be attached to
a specific assessment. Classify each into EXACTLY ONE of these four types:

- "answer_key"             -- model answers or an answer key that lets the
                              student check their own work
- "rubric"                 -- a scoring rubric or descriptors explaining how
                              work is evaluated
- "remediation_referral"   -- explicit guidance on what to do if struggling
                              (e.g. "If you got items 1-3 wrong, review Lesson
                              2", a corrective/remedial activity pointed at
                              specific content)
- "positive_reinforcement" -- encouraging or motivational language framed
                              around the student's performance or effort (e.g.
                              "Great job completing this module!",
                              "Congratulations on finishing!")

STRICT rules:
- Do NOT classify legal disclaimers, copyright notices, fair-use statements,
  reproduction/distribution prohibitions, administrative boilerplate, or
  institutional-policy notices as feedback mechanisms.
- You must quote a minimal evidence quote directly evidencing the feedback
  mechanism. A bare heading with no content (e.g. just "Feedback") is NOT
  sufficient -- still list it, but with empty "evidence".
- List EVERY distinct mechanism you find, even more than one of the same type.
- If a mechanism does not clearly fit one of the four types, do not force it
  -- omit it rather than guessing.

For each mechanism found, put a short label in "text", one of the four types
in "feedback_type", and the minimal evidence quote as evidence.

Return ONLY valid JSON in exactly this shape:
{{{{
  "mechanisms": [
    {{{{\"id\": 1, \"text\": \"short label\", \"feedback_type\": \"answer_key\",
      \"evidence\": \"minimal evidence quote\"}}}}
  ]
}}}}

SLM CONTENT (sampled):
{{content}}
"""


def slice_for_feedback(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample evenly across the whole document (see slicing.downsample).

    Feedback/encouragement can appear anywhere -- not just alongside
    assessments -- so this reads the full document via downsampling instead of
    a single bottom-anchored window.
    """
    return downsample(text, budget=budget, windows=windows)


def _normalize_type(raw: str) -> str:
    """Map free-text type to one of FEEDBACK_TYPES, or "" if unrecognized.

    Matches by prefix/equality against the canonical, underscore-joined form.
    Anything unrecognized normalizes to "" and is dropped -- conservative, so a
    mis-tagged or invented type cannot inflate the count.
    """
    cleaned = raw.strip().lower().replace(" ", "_").replace("-", "_")
    for kind in FEEDBACK_TYPES:
        if cleaned == kind or cleaned.startswith(kind):
            return kind
    return ""


@dataclass
class FeedbackResult:
    score: int
    count: int
    types: list[str]
    mechanisms: list[dict[str, Any]]
    genuine: list[dict[str, Any]]


def compute(mechanisms: list[dict[str, Any]]) -> FeedbackResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    Counts DISTINCT TYPES represented among mechanisms that carry real content
    (the evidence requirement enforces the "must have real content, not just a
    heading" rule), not the number of mechanism instances. Several instances
    of the same type collapse to one entry in the type set -- e.g. three
    answer keys are one mechanism type, not three (mirrors
    varied_assessment.compute; see the module docstring for why this diverges
    from progress_monitoring's instance-counting).
    """
    genuine: list[dict[str, Any]] = []
    types: set[str] = set()
    for mechanism in mechanisms:
        evidence = str(mechanism.get("evidence", "")).strip()
        if not evidence:  # bare heading / no real content -> does not count
            continue
        kind = _normalize_type(str(mechanism.get("feedback_type", "")))
        if not kind:  # unrecognized type -> dropped, not guessed
            continue
        if kind == "positive_reinforcement":
            if _is_high_confidence_boilerplate(evidence) and not _has_explicit_praise(
                evidence
            ):
                continue
        genuine.append(mechanism)
        types.add(kind)

    count = len(types)
    score = count_band(count, THRESHOLDS)
    return FeedbackResult(
        score=score,
        count=count,
        types=sorted(types),
        mechanisms=mechanisms,
        genuine=genuine,
    )


def evaluate(client: Any, text: str) -> FeedbackResult:
    """Thin wrapper: fetch facts from the LLM, then compute the band.

    Used by the CLI to run A-04 standalone. At integration the facts come from
    a shared/grouped call instead, but ``compute`` stays the same.
    """
    content = slice_for_feedback(text)
    raw = client.generate(
        PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1500,
    )
    data = parse_json_payload(raw)
    return compute(list(data.get("mechanisms", [])))


__all__ = [
    "FeedbackResult",
    "compute",
    "evaluate",
    "slice_for_feedback",
    "FEEDBACK_TYPES",
    "THRESHOLDS",
    "PROMPT",
]
