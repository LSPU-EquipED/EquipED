"""Grouping for SME's LLM-direct-scoring calls.

Each group's text slice reuses an EXISTING, already-validated basket slicer
from ``extraction.py`` -- these groups only re-package criteria that already
share an identical slicing scope, so no new slicing behavior is introduced.
See ``docs/superpowers/specs/2026-08-13-sme-dpo-scoring-design.md``.
"""

from __future__ import annotations

from ..oracle import extraction

GROUP_CODES: dict[str, tuple[str, ...]] = {
    "assessment_alignment": ("A-02", "A-05"),
    "task_execution": ("A-01", "A-03", "OP-02", "OP-03", "OP-05"),
    "document_wide": ("OP-01", "OP-04", "A-04"),
}

GROUP_NAMES: tuple[str, ...] = tuple(GROUP_CODES)

CODE_TO_GROUP: dict[str, str] = {
    code: group_name
    for group_name, codes in GROUP_CODES.items()
    for code in codes
}

_SLICERS = {
    "assessment_alignment": extraction.slice_for_basket_a1,
    "task_execution": extraction.slice_for_basket_a2,
    "document_wide": extraction.slice_for_basket_b1,
}


def slice_for_group(group: str, text: str) -> str:
    return _SLICERS[group](text)


__all__ = ["GROUP_CODES", "GROUP_NAMES", "CODE_TO_GROUP", "slice_for_group"]
