"""Whole-document downsampling for Coordinator envelope source text.

Independent copy of the shared helper (see
server/modules/agents/sme/slicing.py) so the coordinator package has no
import-time dependency on the sme package.
"""

from __future__ import annotations

GAP_MARKER = "\n\n[...]\n\n"


def downsample(text: str, *, budget: int = 9000, windows: int = 6) -> str:
    """Sample ``windows`` evenly-spaced chunks spanning the whole document.

    Returns ``text`` unchanged when it already fits ``budget``. Otherwise
    samples ``windows`` chunks of ``budget // windows`` chars from evenly
    spaced start points, joined by ``GAP_MARKER``; the last window is
    anchored to the true end of the document.
    """
    if len(text) <= budget:
        return text

    chunk_size = max(budget // windows, 1)
    chunks: list[str] = []
    for i in range(windows):
        if i == windows - 1:
            start = max(0, len(text) - chunk_size)
        else:
            start = (i * len(text)) // windows
        chunks.append(text[start : start + chunk_size])
    return GAP_MARKER.join(chunks)


__all__ = ["GAP_MARKER", "downsample"]
