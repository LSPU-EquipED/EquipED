"""Shared slicing helpers used by more than one criterion and grouped scoring.

Criteria that judge the MAIN LESSON CONTENT (as opposed to the tasks/
assessments section near the bottom -- see
openspec/specs/sme-engine-scoring/spec.md) need
a different strategy: they must see representative content from across the
WHOLE document, not just one contiguous window, because "coherent from Unit to
Chapter" or "sections have accurate information" is a judgment about the full
sequence, not just its start.
"""

from __future__ import annotations

# Literal marker inserted between sampled windows. Prompts using this slice
# MUST explain what it means -- otherwise the model may mistake an omitted
# span for a real, adjacent transition/section and flag it as broken or
# incoherent, which would be a false finding caused by the slicing itself, not
# the document.
GAP_MARKER = "\n\n[...]\n\n"

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


def downsample(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample ``windows`` evenly-spaced chunks spanning the whole document.

    If ``text`` already fits within ``budget``, it is returned unchanged (no
    need to sample). Otherwise the document is split into ``windows`` equal
    chunks of ``budget // windows`` chars each, taken from evenly-spaced start
    points across the full length, and joined with ``GAP_MARKER``. This gives
    criteria that judge the full lesson sequence (OP-01 coherence, OP-04
    section accuracy) visibility into LATE topics that a single head/tail
    window would miss, at the cost of choppier context across the gaps --
    which is why the gap must be marked, not left silent.

    The LAST window is anchored to the true END of the document (not the
    proportional start point) -- with a chunk size much smaller than
    ``len(text) / windows`` on a long document, a proportionally-placed last
    window would stop well short of the actual ending, missing exactly the
    "Chapter" end that "Unit to Chapter" coherence needs to see.
    """
    if len(text) <= budget:
        return text

    chunk_size = max(budget // windows, 1)
    chunks: list[str] = []
    for i in range(windows):
        if i == windows - 1:
            start = max(0, len(text) - chunk_size)  # anchor to the true tail
        else:
            start = (i * len(text)) // windows
        chunks.append(text[start : start + chunk_size])
    return GAP_MARKER.join(chunks)


def find_section_start(text: str, *, after: int = 0) -> int | None:
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
    start = find_section_start(text, after=head)
    body_part = text[-body:] if start is None else text[start : start + body]
    return head_part + "\n\n[...lecture body omitted...]\n\n" + body_part


def slice_bottom_section(text: str, *, body: int = 9000) -> str:
    """The bottom Performance-Tasks section only, tail-anchored fallback."""
    start = find_section_start(text)
    if start is None:
        return text[-body:] if len(text) > body else text
    return text[start : start + body]


def slice_for_basket_a2(text: str, *, body: int = 9000) -> str:
    """Bottom section only -- tasks (feeds A-01, OP-02, OP-03)."""
    return slice_bottom_section(text, body=body)


def slice_for_basket_b1(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample evenly across the whole document (see slicing.downsample)."""
    return downsample(text, budget=budget, windows=windows)


__all__ = [
    "GAP_MARKER",
    "SECTION_ANCHORS",
    "downsample",
    "find_section_start",
    "slice_for_basket_a1",
    "slice_bottom_section",
    "slice_for_basket_a2",
    "slice_for_basket_b1",
]
