"""OP-01 Topic Coherence: does the SLM's content flow logically from one topic
to the next, Unit to Chapter?

Rubric intent: "Topics are coherent from Unit to Chapter." We measure this as a
COVERAGE RATIO (Pattern A): split the main lesson content into ordered TOPIC
BLOCKS, then judge each consecutive transition as coherent or not.

    coherence_ratio = coherent_transitions / total_transitions

mapped on the moderate scale (>=80% -> 4, >=50% -> 3, >=20% -> 2, else 1).

Short-document fallback (openspec/specs/sme-engine-scoring/spec.md): with FEWER THAN 4
transitions, a percentage swings too wildly for one bad transition to be a fair
signal (e.g. 1 issue out of 2 transitions = 50%, the same score a genuinely
mixed module would get). Below that threshold we instead count ISSUES directly:
0 issues -> 4, 1 -> 3, 2 -> 2, 3+ -> 1. This deliberately does NOT use the
generic "nothing to measure -> score 1" rule -- a short module with zero
incoherent transitions is coherent, not deficient.

Unlike the task-based criteria (A-01/A-02/OP-05/etc., which anchor on the
bottom Performance-Tasks section), coherence is a property of the MAIN LESSON
CONTENT across the whole document. A single ~9k-char window would only see the
first topics, so this uses the shared ``downsample`` helper (see slicing.py) to
sample evenly across the full document instead. The prompt must be told what
the sampling gap marker means, or it may mistake an omitted span for a real,
broken transition.

Shape mirrors clear_directions.py: a pure ``compute`` (facts -> band) plus a
thin ``evaluate`` wrapper the CLI uses to run it standalone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...runtime.llm import parse_json_payload
from .bands import ratio_band
from .slicing import GAP_MARKER, downsample

# Below this many transitions, use the issue-count fallback instead of a ratio
# (openspec/specs/sme-engine-scoring/spec.md).
MIN_TRANSITIONS_FOR_RATIO = 4

# Issue count -> band for the short-document fallback: 0 -> 4, 1 -> 3, 2 -> 2,
# 3+ -> 1.
ISSUE_THRESHOLDS: tuple[tuple[int, int], ...] = ((0, 4), (1, 3), (2, 2))

PROMPT = f"""You are analyzing a Self-Paced Learning Module (SLM).

Your ONLY job is to extract facts. Do NOT assign any score.

NOTE: the content below is SAMPLED from across the whole document -- the marker
"{GAP_MARKER.strip()}" marks a span that was OMITTED to fit the sample. Do NOT
treat a "{GAP_MARKER.strip()}" gap itself as evidence of an incoherent
transition -- only judge transitions between content that is genuinely
adjacent and readable on both sides of a boundary you can see.

1. Split the visible content into an ordered list of TOPIC BLOCKS (each a
   distinct subject/concept the material covers, in the order it appears).
2. For each pair of CONSECUTIVE topic blocks you can directly compare, judge
   whether the transition between them is LOGICAL and COHERENT, using this
   rule: a transition is coherent if the second topic follows sensibly from
   the first (e.g. builds on it, is clearly sequenced, or is explicitly
   connected), and NOT coherent if the jump feels abrupt, unrelated, or
   out of order.
3. Skip any pair that is separated by a "{GAP_MARKER.strip()}" gap -- you
   cannot judge a transition you cannot see.
4. Give a short reason for each judgment.

Return ONLY valid JSON in exactly this shape:
{{{{
  "topics": [{{{{"id": 1, "title": "short topic label"}}}}],
  "transitions": [
    {{{{"from_id": 1, "to_id": 2, "is_coherent": true, "reason": "short reason"}}}}
  ]
}}}}

SLM CONTENT (sampled):
{{content}}
"""


def slice_for_coherence(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample evenly across the whole document (see slicing.downsample)."""
    return downsample(text, budget=budget, windows=windows)


@dataclass
class CoherenceResult:
    score: int
    pct: float | None
    coherent: int
    total: int
    mode: str  # "ratio" or "issue-count"
    topics: list[dict[str, Any]]
    transitions: list[dict[str, Any]]


def compute(
    topics: list[dict[str, Any]], transitions: list[dict[str, Any]]
) -> CoherenceResult:
    """Pure measurement -> band. No LLM, no IO -- fully unit-testable.

    No topics at all -> nothing is assessable -> score 1 (empty rule).
    Fewer than MIN_TRANSITIONS_FOR_RATIO transitions -> issue-count fallback
    (a short module with 0 issues is coherent, not deficient -- this
    intentionally does NOT fall back to the generic empty-denominator rule).
    Otherwise -> ratio_band on the moderate scale.
    """
    if not topics:
        return CoherenceResult(
            score=1,
            pct=None,
            coherent=0,
            total=0,
            mode="issue-count",
            topics=[],
            transitions=[],
        )

    # Dedupe by (from_id, to_id) so a repeated transition entry cannot inflate
    # either the denominator or the coherent count (the class of bug that
    # inflated A-05 to 10/3).
    seen: set[tuple[Any, Any]] = set()
    unique_transitions: list[dict[str, Any]] = []
    for t in transitions:
        key = (t.get("from_id"), t.get("to_id"))
        if key in seen:
            continue
        seen.add(key)
        unique_transitions.append(t)
    transitions = unique_transitions

    total = len(transitions)
    coherent = sum(1 for t in transitions if t.get("is_coherent"))

    if total < MIN_TRANSITIONS_FOR_RATIO:
        issues = total - coherent
        score = 1
        for max_issues, band in ISSUE_THRESHOLDS:
            if issues <= max_issues:
                score = band
                break
        return CoherenceResult(
            score=score,
            pct=None,
            coherent=coherent,
            total=total,
            mode="issue-count",
            topics=topics,
            transitions=transitions,
        )

    band = ratio_band(coherent, total, scale="moderate")
    return CoherenceResult(
        score=band.band,
        pct=band.pct,
        coherent=coherent,
        total=total,
        mode="ratio",
        topics=topics,
        transitions=transitions,
    )


def evaluate(client: Any, text: str) -> CoherenceResult:
    """Thin wrapper: fetch facts from the LLM, then compute the band.

    Used by the CLI to run OP-01 standalone. At integration the facts come
    from a shared/grouped call instead, but ``compute`` stays the same.
    """
    content = slice_for_coherence(text)
    raw = client.generate(
        PROMPT.format(content=content),
        temperature=0.0,  # determinism: see spike findings
        max_new_tokens=1800,
    )
    data = parse_json_payload(raw)
    return compute(
        topics=list(data.get("topics", [])),
        transitions=list(data.get("transitions", [])),
    )


__all__ = [
    "CoherenceResult",
    "compute",
    "evaluate",
    "slice_for_coherence",
    "MIN_TRANSITIONS_FOR_RATIO",
    "ISSUE_THRESHOLDS",
    "PROMPT",
]
