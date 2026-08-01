"""Deterministic extraction of the standard LSPU syllabus outcomes table."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from .exceptions import ExtractionFailedError


class PageText(Protocol):
    page_number: int
    text: str
    is_ocr: bool


_TABLE_HEADING_RE = re.compile(
    r"\b(?:course\s+learning\s+outcomes?|course\s+outcomes?)\b", re.IGNORECASE
)
_COLUMN_HEADER_RE = re.compile(
    r"\b(?:code|outcome\s+code)\b.*\b(?:outcome|description)\b", re.IGNORECASE
)
_CODE_HEADER_RE = re.compile(r"^\s*(?:code|outcome\s+code)\s*$", re.IGNORECASE)
_OUTCOME_HEADER_RE = re.compile(
    r"^\s*(?:course\s+)?(?:learning\s+)?outcomes?(?:\s+description)?\s*$",
    re.IGNORECASE,
)
_ROW_RE = re.compile(
    r"^\s*((?:CLO|CO|LO)\s*[-.]?\s*\d+[A-Z]?)\s*"
    r"(?:[|:\-–—]\s*)?(.*?)\s*$",
    re.IGNORECASE,
)
_SECTION_END_RE = re.compile(
    r"^\s*(?:assessment|grading|course\s+content|learning\s+plan|references|"
    r"teaching\s+and\s+learning|policies)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SyllabusOutcomeRecord:
    code: str
    description: str
    page_number: int
    row_index: int
    is_ocr: bool


def extract_syllabus_outcomes(pages: list[PageText]) -> list[SyllabusOutcomeRecord]:
    """Extract exactly one recognized outcomes table and fail closed otherwise."""

    heading_locations: list[tuple[int, int]] = []
    for page_index, page in enumerate(pages):
        for line_index, line in enumerate(page.text.splitlines()):
            if _TABLE_HEADING_RE.search(line):
                heading_locations.append((page_index, line_index))

    # Repeated table headings on continuation pages are acceptable only when
    # they are consecutive; separated headings represent ambiguous tables.
    if not heading_locations:
        raise ExtractionFailedError(
            "No Course Outcomes or Course Learning Outcomes table was found."
        )
    heading_pages = sorted({page_index for page_index, _ in heading_locations})
    if any(b - a > 1 for a, b in zip(heading_pages, heading_pages[1:], strict=False)):
        raise ExtractionFailedError(
            "Multiple ambiguous syllabus outcomes tables were found."
        )

    start_page, start_line = heading_locations[0]
    records: list[SyllabusOutcomeRecord] = []
    current: tuple[str, list[str], int, bool] | None = None
    saw_code_header = False
    saw_outcome_header = False

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        code, parts, page_number, is_ocr = current
        description = " ".join(" ".join(parts).split()).strip(" |:-–—")
        if len(description.split()) < 3:
            raise ExtractionFailedError(f"Malformed syllabus outcome row: {code}.")
        records.append(
            SyllabusOutcomeRecord(
                code=_normalize_code(code),
                description=description,
                page_number=page_number,
                row_index=len(records),
                is_ocr=is_ocr,
            )
        )
        current = None

    for page_index in range(start_page, len(pages)):
        page = pages[page_index]
        lines = page.text.splitlines()
        line_start = start_line + 1 if page_index == start_page else 0
        for raw_line in lines[line_start:]:
            line = " ".join(raw_line.split()).strip()
            if not line:
                continue
            combined_header = bool(_COLUMN_HEADER_RE.search(line))
            table_heading = bool(_TABLE_HEADING_RE.search(line))
            if combined_header or (not table_heading and _CODE_HEADER_RE.match(line)):
                saw_code_header = True
            if combined_header or (
                not table_heading and _OUTCOME_HEADER_RE.match(line)
            ):
                saw_outcome_header = True
            if (
                table_heading
                or combined_header
                or _CODE_HEADER_RE.match(line)
                or _OUTCOME_HEADER_RE.match(line)
            ):
                continue
            if current is not None and _SECTION_END_RE.match(line):
                flush()
                break
            match = _ROW_RE.match(line)
            if match:
                flush()
                parts = [match.group(2)] if match.group(2).strip() else []
                current = (match.group(1), parts, page.page_number, page.is_ocr)
                continue
            if current is not None:
                current[1].append(line)
        else:
            continue
        break
    flush()

    if not (saw_code_header and saw_outcome_header):
        raise ExtractionFailedError(
            "The syllabus outcomes table is missing required code and outcome columns."
        )
    if not records:
        raise ExtractionFailedError(
            "The syllabus outcomes table contains no valid rows."
        )
    codes = [record.code for record in records]
    if len(codes) != len(set(codes)):
        raise ExtractionFailedError(
            "The syllabus outcomes table contains duplicate codes."
        )
    return records


def _normalize_code(value: str) -> str:
    return re.sub(r"[\s.\-]+", "", value).upper()


__all__ = ["SyllabusOutcomeRecord", "extract_syllabus_outcomes"]
