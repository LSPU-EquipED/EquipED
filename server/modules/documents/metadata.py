"""Regex-based metadata detection for document preprocessing.

Extracts program, academic_year, course_code, and lesson_title from the first
~6000 characters of document text using pure regex pattern matching.
No LLM calls, no new dependencies beyond Python's built-in ``re`` module.
"""

from __future__ import annotations

import re

_DETECTION_PROGRAMS = (
    "BSInfoTech",
    "BSIT",
    "BSCS",
)

# Pre-compile patterns once at module load
_PROGRAM_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(_DETECTION_PROGRAMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def canonicalize_supported_program(value: str | None) -> str | None:
    """Return the canonical active program code, or ``None`` if unsupported."""
    if not value or not value.strip():
        return None
    normalized = value.strip().casefold()
    if normalized in {"bsinfotech", "bsit"}:
        return "BSInfoTech"
    if normalized == "bscs":
        return "BSCS"
    return None


# Academic year patterns: "2025-2026", "2025 – 2026", "AY 2025", "SY 2025-2026"
_ACADEMIC_YEAR_PATTERN = re.compile(
    r"\b(?:SY\s*)?(20\d{2})\s*[–-]\s*(20\d{2})\b"
    r"|"
    r"\b(?:AY|SY)\s*(20\d{2})\b"
)

# Course code patterns: "CCS 101", "IT 201", "MATH 101"
_COURSE_CODE_PATTERN = re.compile(r"\b([A-Z]{2,4})\s*(\d{3})\b")

_DETECTION_LIMIT = 6000

# Lesson title pattern: "Lesson Title: <value>"
_LESSON_TITLE_PATTERN = re.compile(
    r"Lesson\s+Title[:\-]\s*([^\n]+)", re.MULTILINE | re.IGNORECASE
)


def detect_metadata(text: str, title: str | None = None) -> dict[str, str | None]:
    """Extract program, academic_year, course_code, lesson_title from text and title.

    Only scans the first ~6000 characters (first 2-3 pages) to reduce
    false positives from body text. If program or course_code is not found
    in body text, falls back to the document title.
    """
    head = text[:_DETECTION_LIMIT]
    detected_prog = _detect_program(head)
    detected_cc = _detect_course_code(head)
    if title:
        if not detected_prog:
            detected_prog = _detect_program(title)
        if not detected_cc:
            detected_cc = _detect_course_code(title)

    return {
        "program": detected_prog,
        "academic_year": _detect_academic_year(head),
        "course_code": detected_cc,
        "lesson_title": _detect_lesson_title(head),
    }


def _detect_program(text: str) -> str | None:
    """Match known LSPU SCC program codes, rejecting false positives.

    Filters out common false-positive acronyms like PDF, URL, HTTP, HTML.
    The legacy ``BSIT`` alias is canonicalized to ``BSInfoTech`` so stored
    document programs always use the canonical code.
    """
    seen: set[str] = set()
    candidates: list[str] = []
    for match in _PROGRAM_PATTERN.finditer(text):
        code = canonicalize_supported_program(match.group(1))
        if code is None:
            continue
        if code not in seen:
            seen.add(code)
            candidates.append(code)

    return candidates[0] if candidates else None


def _detect_academic_year(text: str) -> str | None:
    """Match academic year patterns.

    Normalizes matches to the format ``"2025-2026"`` or ``"AY 2025"``.
    """
    for match in _ACADEMIC_YEAR_PATTERN.finditer(text):
        # Pattern 1: "2025-2026" or "SY 2025-2026"
        year1, year2 = match.group(1), match.group(2)
        if year1 and year2:
            return f"{year1}-{year2}"
        # Pattern 2: "AY 2025" or "SY 2025"
        ay_year = match.group(3)
        if ay_year:
            return f"AY {ay_year}"
    return None


def _detect_course_code(text: str) -> str | None:
    """Match course code patterns like ``"CCS 101"``, ``"CMSC 313"``.

    Returns the first match found in the text head.
    """
    match = _COURSE_CODE_PATTERN.search(text)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return None


def _detect_lesson_title(text: str) -> str | None:
    """Match ``Lesson Title: <value>`` labels on cover pages.

    Returns the captured value stripped of leading/trailing whitespace,
    or None if no match is found.
    """
    match = _LESSON_TITLE_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


__all__: list[str] = [
    "detect_metadata",
    "canonicalize_supported_program",
    "_detect_program",
    "_detect_academic_year",
    "_detect_course_code",
    "_detect_lesson_title",
]
