"""Whole-document downsampling shared by evaluation agents.

Adapted from ``server/modules/agents/sme/prompt.py:24-51``. Samples
evenly-spaced windows spanning the entire document so late-document
content stays visible within a fixed character budget.
"""

from __future__ import annotations

from server.modules.agents.exceptions import AgentExecutionError

# Literal marker inserted between sampled windows. Prompts using this slice
# MUST explain what it means -- otherwise the model may mistake an omitted
# span for a real, adjacent transition/section and flag it as broken or
# incoherent, which would be a false finding caused by the slicing itself, not
# the document.
GAP_MARKER = "\n\n[...]\n\n"


def downsample_source_text(
    text: str,
    budget: int,
    windows: int = 6,
    gap_marker: str = GAP_MARKER,
) -> str:
    """Sample evenly-spaced windows spanning the entire document.

    Ensures the final length is strictly <= budget and the last window is
    anchored to the true tail of the document. Gap markers are subtracted
    from the budget before sizing chunks, so no trailing hard slice -- and
    no mid-word tail chop -- is needed to stay within budget.
    """
    if windows < 1:
        raise AgentExecutionError("downsample windows must be >= 1")
    if len(text) <= budget:
        return text
    if budget <= len(gap_marker):
        raise AgentExecutionError("source budget cannot mark omitted content")

    total_gaps_len = (windows - 1) * len(gap_marker)
    if budget <= total_gaps_len + windows:
        raise AgentExecutionError("source budget cannot mark omitted content")

    chunk_size = max(1, (budget - total_gaps_len) // windows)
    chunks: list[str] = []
    for i in range(windows):
        if i == windows - 1:
            start = max(0, len(text) - chunk_size)  # True tail
        else:
            start = (i * len(text)) // windows
        chunks.append(text[start : start + chunk_size])

    sampled = gap_marker.join(chunks)
    if len(sampled) > budget:
        # Unreachable by construction (windows*chunk+gaps <= budget), but
        # guard against rounding drift without chopping the tail mid-word:
        # back off to the last whitespace within budget.
        cut = -1
        for sep in (" ", "\n", "\t"):
            idx = sampled.rfind(sep, 0, budget + 1)
            if idx > cut:
                cut = idx
        if cut > 0:
            sampled = sampled[:cut]
        else:
            sampled = sampled[:budget]
    return sampled


__all__ = ["GAP_MARKER", "downsample_source_text"]
