"""Shared text-slicing helpers for SME's grouped-LLM scoring calls.

These slicers originally fed a retired 6-basket fact-extraction pass (see
``registry.py``'s history before this trim); ``groups.py``'s
``slice_for_group`` now reuses the same validated slicing scope directly for
each of the 3 grouped-scoring calls, so no new slicing behavior is
introduced by the current scoring path.

OP-02 and OP-03 anchor on the same SECTION_ANCHORS bottom section as
A-01/A-03/OP-05 -- a deliberate, validated change from an older
head+vocabulary slice that was pulling lecture content into the tasks scope.
"""

from __future__ import annotations

from .slicing import downsample

# Same bottom-section anchors used by learner_transformation / varied_assessment
# / progress_monitoring / enhancement_activities -- the fullest variant (with
# "questions for reflection"), since the task-execution group also has to
# cover what OP-02/OP-03 used to read via their own vocabulary markers.
SECTION_ANCHORS: tuple[str, ...] = (
    "performance task",
    "performance tasks",
    "learning tasks",
    "enrichment activit",
    "enhancement activit",
    "assessment task",
    "questions for reflection",
)


def _find_section_start(text: str, *, after: int = 0) -> int | None:
    """Earliest SECTION_ANCHORS match at or after ``after``, or None."""
    lower = text.lower()
    start: int | None = None
    for anchor in SECTION_ANCHORS:
        idx = lower.find(anchor, after)
        if idx != -1 and (start is None or idx < start):
            start = idx
    return start


def slice_for_basket_a1(text: str, *, head: int = 4000, body: int = 7000) -> str:
    """Objectives head + the bottom Performance-Tasks section, for the
    assessment-alignment group (A-02, A-05).
    """
    if len(text) <= head + body:
        return text
    head_part = text[:head]
    start = _find_section_start(text, after=head)
    body_part = text[-body:] if start is None else text[start : start + body]
    return head_part + "\n\n[...lecture body omitted...]\n\n" + body_part


def _slice_bottom_section(text: str, *, body: int = 9000) -> str:
    """The bottom Performance-Tasks section only, tail-anchored fallback."""
    start = _find_section_start(text)
    if start is None:
        return text[-body:] if len(text) > body else text
    return text[start : start + body]


def slice_for_basket_a2(text: str, *, body: int = 9000) -> str:
    """Bottom section only -- tasks (feeds A-01, OP-02, OP-03)."""
    return _slice_bottom_section(text, body=body)


def slice_for_basket_b1(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample evenly across the whole document (see slicing.downsample)."""
    return downsample(text, budget=budget, windows=windows)


__all__ = [
    "SECTION_ANCHORS",
    "slice_for_basket_a1",
    "slice_for_basket_a2",
    "slice_for_basket_b1",
]
