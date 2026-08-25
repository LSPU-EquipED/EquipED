"""Deterministic section-aware curriculum map text extraction and filtering."""

from __future__ import annotations

import re
from typing import NamedTuple

from ..exceptions import ExtractionFailedError
from ..ingestion.pipeline import ExtractedPage

# Matches: "Curriculum Map for the Bachelor of Science in <Program>"
CURRICULUM_MAP_HEADER_RE = re.compile(
    r"Curriculum\s+Map\s+for\s+the\s+Bachelor\s+of\s+Science\s+in\s+([^\n\r]+)",
    re.IGNORECASE,
)

# End-of-map markers: "Section 11", "Sample Means of Curriculum Delivery"
# Anchored to heading lines only.
END_MARKERS_RE = re.compile(
    r"(?m)^\s*(?:"
    r"Section\s+11(?:\s*[:.\-—–]+\s*|\s+)?(?:Sample\s+Means\s+of\s+Curriculum\s+Delivery)?"
    r"|"
    r"Sample\s+Means\s+of\s+Curriculum\s+Delivery"
    r")\s*[:.\-—–]*\s*$",
    re.IGNORECASE,
)

OTHER_PROGRAM_PATTERNS = {
    "BSCS": re.compile(
        r"(?:\bBachelor\s+of\s+Science\s+in\s+(?:Information\s+Technology|Information\s+Systems|Entertainment\s+and\s+Multimedia\s+Computing)\b|\b(?:BSInfoTech|BSIT|BSIS|BSEMC)\b)",
        re.IGNORECASE,
    ),
    "BSInfoTech": re.compile(
        r"(?:\bBachelor\s+of\s+Science\s+in\s+(?:Computer\s+Science|Information\s+Systems|Entertainment\s+and\s+Multimedia\s+Computing)\b|\b(?:BSCS|BSIS|BSEMC)\b)",
        re.IGNORECASE,
    ),
}


def _normalize_program_from_header(raw_program_text: str) -> str | None:
    norm = raw_program_text.strip().casefold()
    if norm.startswith("computer science") or norm.startswith("cs"):
        return "BSCS"
    if norm.startswith("information technology") or norm.startswith("it"):
        return "BSInfoTech"
    if norm.startswith("information systems") or norm.startswith("is"):
        return "BSIS"
    if norm.startswith("entertainment and multimedia computing") or norm.startswith(
        "emc"
    ):
        return "BSEMC"
    return norm.split()[0] if norm else None


class BoundaryMarker(NamedTuple):
    page_index: int
    char_offset: int
    marker_type: str  # "program" or "end"
    program_code: str | None


def filter_curriculum_pages(
    pages: list[ExtractedPage],
    target_program: str,
) -> list[ExtractedPage]:
    """Filter extracted PDF pages to retain only the selected canonical program section.

    Handles same-page boundaries, recognizes multi-program headers,
    stops at the next program header or Section 11/Sample Means of Curriculum Delivery,
    and fails closed on absent sections or unbounded multi-program indicators.
    """
    if not pages:
        raise ExtractionFailedError("No pages provided for curriculum filtering")

    if any(not page.text.strip() for page in pages):
        raise ExtractionFailedError(
            "Curriculum document contains empty or unextractable pages"
        )

    if target_program not in ("BSCS", "BSInfoTech"):
        raise ExtractionFailedError(
            f"Unsupported curriculum target program: {target_program}"
        )

    # Collect all boundary markers across all pages in reading order
    markers: list[BoundaryMarker] = []
    for page_idx, page in enumerate(pages):
        text = page.text

        for match in CURRICULUM_MAP_HEADER_RE.finditer(text):
            prog_code = _normalize_program_from_header(match.group(1))
            markers.append(
                BoundaryMarker(
                    page_index=page_idx,
                    char_offset=match.start(),
                    marker_type="program",
                    program_code=prog_code,
                )
            )

        for match in END_MARKERS_RE.finditer(text):
            markers.append(
                BoundaryMarker(
                    page_index=page_idx,
                    char_offset=match.start(),
                    marker_type="end",
                    program_code=None,
                )
            )

    # Sort markers chronologically by (page_index, char_offset)
    markers.sort(key=lambda m: (m.page_index, m.char_offset))

    # Check if there are any program map headers
    program_markers = [m for m in markers if m.marker_type == "program"]

    if not program_markers:
        # Case B: No program map headers found.
        # Check for other-program indicators.
        other_pattern = OTHER_PROGRAM_PATTERNS.get(target_program)
        if other_pattern:
            for page in pages:
                if other_pattern.search(page.text):
                    raise ExtractionFailedError(
                        "Multi-program curriculum indicators detected but "
                        "deterministic section boundaries could not be resolved."
                    )

        # Single-program curriculum with no headers/indicators -> retain all pages
        return list(pages)

    # Case A: Program map headers found.
    # Find matching target program marker
    target_marker_index = None
    for idx, marker in enumerate(markers):
        if marker.marker_type == "program" and marker.program_code == target_program:
            target_marker_index = idx
            break

    if target_marker_index is None:
        # Detected map headers, but none matched target program
        raise ExtractionFailedError(
            f"Curriculum map section for {target_program} not found in document"
        )

    start_marker = markers[target_marker_index]
    end_marker = None

    # End is next marker after start_marker (another program or an end marker)
    if target_marker_index + 1 < len(markers):
        end_marker = markers[target_marker_index + 1]

    filtered_pages: list[ExtractedPage] = []

    start_page_idx = start_marker.page_index
    end_page_idx = end_marker.page_index if end_marker else len(pages) - 1

    for p_idx in range(start_page_idx, end_page_idx + 1):
        orig_page = pages[p_idx]
        text = orig_page.text

        start_char = start_marker.char_offset if p_idx == start_page_idx else 0
        end_char = (
            end_marker.char_offset
            if (end_marker and p_idx == end_page_idx)
            else len(text)
        )

        trimmed_text = text[start_char:end_char]
        if trimmed_text.strip():
            filtered_pages.append(
                ExtractedPage(
                    page_number=orig_page.page_number,
                    text=trimmed_text,
                    is_ocr=orig_page.is_ocr,
                )
            )

    if not filtered_pages:
        raise ExtractionFailedError(
            f"Extracted curriculum section for {target_program} contains no usable text"
        )

    # Scan the retained output range for unresolved indicators of OTHER programs
    other_pattern = OTHER_PROGRAM_PATTERNS.get(target_program)
    if other_pattern:
        for page in filtered_pages:
            if other_pattern.search(page.text):
                raise ExtractionFailedError(
                    "Multi-program curriculum indicators detected in retained section "
                    "without clean section boundary."
                )

    return filtered_pages


__all__ = ["filter_curriculum_pages"]
