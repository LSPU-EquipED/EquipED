"""Shared slicing helpers used by more than one criterion.

Criteria that judge the MAIN LESSON CONTENT (as opposed to the tasks/
assessments section near the bottom -- see docs/sme-scoring-basis.md s.3) need
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


__all__ = ["GAP_MARKER", "downsample"]
