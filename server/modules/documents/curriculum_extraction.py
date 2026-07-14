"""Per-course extraction for curriculum (CHED CMO) reference documents.

CHED CMOs lay course specifications out as a two-column table (field labels
on the left, values on the right). Scanned PDFs have no text layer, so OCR-ing
a full page flattens that table into scrambled reading order (labels and
values interleaved wrong). This module OCRs each course-spec page as a
label/value column split instead, then keeps the longest prose block in the
value column as the course description.

Validated against a single-course-per-page CMO layout (courses each get their
own page, with a "Course Name"/"COURSE NAME" header line). CMOs that pack
several courses onto one page are not handled here; `extract_curriculum_courses`
returns no record for pages where no title line is found, and callers should
fall back to generic chunking for a document where extraction yields too few
records to be useful.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

_TITLE_RE = re.compile(
    r"(?:COURSE NAME|Course Name)\s*\n?\s*([A-Za-z][A-Za-z0-9 &\-,.]{2,60})"
)
_GUTTER_SEARCH_LO_FRAC = 0.30
_GUTTER_SEARCH_HI_FRAC = 0.70
_GUTTER_DENSITY_PERCENTILE = 40
_MIN_DESCRIPTION_WORDS = 8


@dataclass(slots=True)
class CourseRecord:
    page_number: int
    course_title: str
    course_description: str


def extract_curriculum_courses(file_path: str) -> list[CourseRecord]:
    """Extract one CourseRecord per course-spec page found in a curriculum PDF."""

    try:
        import fitz
    except ModuleNotFoundError:
        return []

    try:
        import pytesseract
    except ModuleNotFoundError:
        return []

    try:
        from PIL import Image
    except ModuleNotFoundError:
        return []

    records: list[CourseRecord] = []
    with fitz.open(file_path) as doc:
        for index, page in enumerate(doc, start=1):
            selectable = (page.get_text() or "").strip()
            title = _find_title(selectable)

            pixmap = page.get_pixmap(dpi=250)
            image = Image.frombytes(
                "RGB", [pixmap.width, pixmap.height], pixmap.samples
            )

            if title is None:
                ocr_text = _safe_ocr_string(pytesseract, image)
                title = _find_title(ocr_text)
                if title is None:
                    continue

            description = _extract_description(pytesseract, image)
            if not description:
                continue

            records.append(
                CourseRecord(
                    page_number=index,
                    course_title=title,
                    course_description=description,
                )
            )

    return records


def _find_title(text: str) -> str | None:
    match = _TITLE_RE.search(text)
    if not match:
        return None
    title = match.group(1).strip()
    return title or None


def _extract_description(pytesseract_module, image) -> str:
    gutter_x = _find_gutter_x(image)
    right_half = image.crop((gutter_x, 0, image.width, image.height))
    right_text = _safe_ocr_string(pytesseract_module, right_half)
    description = _longest_prose_block(right_text)
    if description:
        return description
    whole_text = _safe_ocr_string(pytesseract_module, image)
    return _longest_prose_block(whole_text)


def _safe_ocr_string(pytesseract_module, image) -> str:
    try:
        return pytesseract_module.image_to_string(image)
    except Exception:
        return ""


def _find_gutter_x(image) -> int:
    gray = np.array(image.convert("L"), dtype=np.float32)
    col_density = 255 - gray.mean(axis=0)
    width = len(col_density)
    lo = int(width * _GUTTER_SEARCH_LO_FRAC)
    hi = int(width * _GUTTER_SEARCH_HI_FRAC)
    window = col_density[lo:hi]
    if len(window) == 0:
        return width // 2

    threshold = np.percentile(col_density, _GUTTER_DENSITY_PERCENTILE)
    best_start, best_len, cur_start, cur_len = 0, 0, 0, 0
    for i, value in enumerate(window):
        if value <= threshold:
            if cur_len == 0:
                cur_start = i
            cur_len += 1
            if cur_len > best_len:
                best_len, best_start = cur_len, cur_start
        else:
            cur_len = 0

    return lo + best_start + best_len // 2


def _longest_prose_block(text: str) -> str:
    blocks = re.split(r"\n\s*\n", text)
    candidates = []
    for block in blocks:
        clean = " ".join(block.split())
        word_count = len(clean.split())
        sentence_like = clean.count(".") >= 1 or word_count > 15
        if word_count >= _MIN_DESCRIPTION_WORDS and sentence_like:
            candidates.append(clean)
    if not candidates:
        return ""
    return max(candidates, key=len)


__all__ = ["CourseRecord", "extract_curriculum_courses"]
