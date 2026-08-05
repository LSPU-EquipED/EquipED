"""Deterministic extraction of the syllabus ``Course Contents`` column.

PyMuPDF detects the table and supplies cell geometry.  Once the named column
has been found, its normalized horizontal position is carried to consecutive
pages so continuation tables do not need to repeat their column headers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .exceptions import ExtractionFailedError


class PageText(Protocol):
    page_number: int
    text: str
    is_ocr: bool


_COURSE_CONTENTS_RE = re.compile(r"^course\s+contents?$", re.IGNORECASE)
_GEOMETRY_TOLERANCE = 0.035


@dataclass(frozen=True, slots=True)
class SyllabusCourseContentRecord:
    content: str
    page_number: int
    row_index: int
    is_ocr: bool


@dataclass(frozen=True, slots=True)
class _TableSignature:
    column_count: int
    target_column: int
    table_x0: float
    table_x1: float
    column_x0: float
    column_x1: float


@dataclass(frozen=True, slots=True)
class _LocatedTable:
    table: Any
    matrix: list[list[str | None]]
    header_row: int
    target_column: int
    signature: _TableSignature


def extract_syllabus_course_contents(
    file_path: str,
    pages: list[PageText],
) -> list[SyllabusCourseContentRecord]:
    """Extract only Course Contents cells from one unambiguous syllabus table.

    Headerless tables on immediately following pages are accepted when their
    column geometry matches the table where the Course Contents header was
    found.  Processing stops at the first page without a matching continuation
    table, preventing unrelated later tables from being included.
    """

    pdf = Path(file_path)
    if not pdf.exists():
        raise ExtractionFailedError(f"File not found: {file_path}")

    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise ExtractionFailedError("PyMuPDF is not installed") from exc

    page_metadata = {page.page_number: page for page in pages}
    located: list[tuple[int, _LocatedTable]] = []

    try:
        with fitz.open(pdf) as document:
            for page_index, page in enumerate(document):
                page_number = page_index + 1
                for table in page.find_tables().tables:
                    match = _locate_course_contents_header(table, page.rect.width)
                    if match is not None:
                        located.append((page_number, match))

            if not located:
                raise ExtractionFailedError(
                    "No table with a Course Contents column was found."
                )
            if len(located) > 1:
                heading_pages = [page_number for page_number, _match in located]
                first_signature = located[0][1].signature
                repeated_continuation_headers = (
                    len(set(heading_pages)) == len(heading_pages)
                    and all(
                        right == left + 1
                        for left, right in zip(
                            heading_pages, heading_pages[1:], strict=False
                        )
                    )
                    and all(
                        _signatures_match(match.signature, first_signature)
                        for _page_number, match in located[1:]
                    )
                )
                if not repeated_continuation_headers:
                    raise ExtractionFailedError(
                        "Multiple ambiguous Course Contents tables were found."
                    )

            start_page_number, start = located[0]
            records: list[SyllabusCourseContentRecord] = []
            _append_table_records(
                records,
                start,
                start_page_number,
                page_metadata,
                first_data_row=start.header_row + 1,
            )

            for page_number in range(start_page_number + 1, len(document) + 1):
                page = document[page_number - 1]
                candidates = [
                    table
                    for table in page.find_tables().tables
                    if _matches_signature(table, page.rect.width, start.signature)
                ]
                if not candidates:
                    break
                if len(candidates) > 1:
                    raise ExtractionFailedError(
                        "The Course Contents continuation table is ambiguous on "
                        f"page {page_number}."
                    )

                table = candidates[0]
                matrix = _extract_matrix(table)
                repeated_header = _find_header_cell(matrix)
                first_data_row = (
                    repeated_header[0] + 1 if repeated_header is not None else 0
                )
                continuation = _LocatedTable(
                    table=table,
                    matrix=matrix,
                    header_row=first_data_row - 1,
                    target_column=start.target_column,
                    signature=start.signature,
                )
                _append_table_records(
                    records,
                    continuation,
                    page_number,
                    page_metadata,
                    first_data_row=first_data_row,
                )
    except ExtractionFailedError:
        raise
    except Exception as exc:
        raise ExtractionFailedError(
            "The Course Contents table could not be extracted."
        ) from exc

    if not records:
        raise ExtractionFailedError(
            "The Course Contents table contains no extractable content."
        )
    return records


def _locate_course_contents_header(
    table: Any, page_width: float
) -> _LocatedTable | None:
    matrix = _extract_matrix(table)
    header = _find_header_cell(matrix)
    if header is None:
        return None
    header_row, target_column = header
    signature = _table_signature(table, page_width, target_column)
    if signature is None:
        return None
    return _LocatedTable(
        table=table,
        matrix=matrix,
        header_row=header_row,
        target_column=target_column,
        signature=signature,
    )


def _find_header_cell(matrix: list[list[str | None]]) -> tuple[int, int] | None:
    matches: list[tuple[int, int]] = []
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            if _COURSE_CONTENTS_RE.fullmatch(_normalize_cell(value)):
                matches.append((row_index, column_index))
    if len(matches) > 1:
        raise ExtractionFailedError(
            "A table contains multiple ambiguous Course Contents columns."
        )
    return matches[0] if matches else None


def _matches_signature(
    table: Any, page_width: float, expected: _TableSignature
) -> bool:
    if int(getattr(table, "col_count", 0)) != expected.column_count:
        return False
    signature = _table_signature(table, page_width, expected.target_column)
    if signature is None:
        return False
    return _signatures_match(signature, expected)


def _signatures_match(
    actual: _TableSignature, expected: _TableSignature
) -> bool:
    if (
        actual.column_count != expected.column_count
        or actual.target_column != expected.target_column
    ):
        return False
    return all(
        abs(observed - wanted) <= _GEOMETRY_TOLERANCE
        for observed, wanted in (
            (actual.table_x0, expected.table_x0),
            (actual.table_x1, expected.table_x1),
            (actual.column_x0, expected.column_x0),
            (actual.column_x1, expected.column_x1),
        )
    )


def _table_signature(
    table: Any, page_width: float, target_column: int
) -> _TableSignature | None:
    if page_width <= 0 or target_column < 0:
        return None
    column_count = int(getattr(table, "col_count", 0))
    if target_column >= column_count:
        return None
    table_bbox = getattr(table, "bbox", None)
    if table_bbox is None:
        return None

    target_cell = None
    for row in getattr(table, "rows", []):
        cells = getattr(row, "cells", [])
        if target_column < len(cells) and cells[target_column] is not None:
            target_cell = cells[target_column]
            break
    if target_cell is None:
        return None

    return _TableSignature(
        column_count=column_count,
        target_column=target_column,
        table_x0=float(table_bbox[0]) / page_width,
        table_x1=float(table_bbox[2]) / page_width,
        column_x0=float(target_cell[0]) / page_width,
        column_x1=float(target_cell[2]) / page_width,
    )


def _append_table_records(
    records: list[SyllabusCourseContentRecord],
    located: _LocatedTable,
    page_number: int,
    page_metadata: dict[int, PageText],
    *,
    first_data_row: int,
) -> None:
    metadata = page_metadata.get(page_number)
    is_ocr = bool(metadata.is_ocr) if metadata is not None else False
    for row in located.matrix[first_data_row:]:
        if located.target_column >= len(row):
            continue
        content = _normalize_cell(row[located.target_column])
        if not content:
            continue
        records.append(
            SyllabusCourseContentRecord(
                content=content,
                page_number=page_number,
                row_index=len(records),
                is_ocr=is_ocr,
            )
        )


def _extract_matrix(table: Any) -> list[list[str | None]]:
    matrix = table.extract()
    return [list(row) for row in matrix] if matrix else []


def _normalize_cell(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


__all__ = ["SyllabusCourseContentRecord", "extract_syllabus_course_contents"]
