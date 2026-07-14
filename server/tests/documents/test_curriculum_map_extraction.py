"""Tests for `extract_curriculum_map_courses` (multi-program CMO layout).

Covers the CMO No. 25 s. 2015 style document (BSCS/BSIS/BSIT sharing one
PDF, courses laid out under "Curriculum Map for the Bachelor of Science in
<Program>" section headers) — distinct from the single-course-per-page
layout `extract_curriculum_courses` already handles.

Uses a fake `fitz` module so these run without real OCR: each fake page
returns selectable text directly via `get_text()`, well past the
extractor's OCR-fallback threshold.
"""

from __future__ import annotations

import sys
import types

from server.modules.documents.curriculum_extraction import (
    DEFAULT_INCLUDED_PROGRAMS,
    extract_curriculum_map_courses,
    map_keywords_for_program,
)

_FILLER = " filler" * 10  # pad past the OCR-fallback length threshold


class _FakePage:
    def __init__(self, text: str):
        self._text = text

    def get_text(self) -> str:
        return self._text


class _FakeDoc:
    def __init__(self, pages: list[_FakePage]):
        self._pages = pages

    def __enter__(self) -> _FakeDoc:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def __iter__(self):
        return iter(self._pages)


def _install_fake_fitz(monkeypatch, pages: list[_FakePage]) -> None:
    fake_fitz = types.ModuleType("fitz")
    fake_fitz.open = lambda path: _FakeDoc(pages)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)


def _cs_it_is_pages() -> list[_FakePage]:
    return [
        _FakePage("front matter" + _FILLER),
        _FakePage(
            "Curriculum Map for the Bachelor of Science in Computer Science\n"
            + _FILLER
            + " CC101 CC102"
        ),
        _FakePage("more CS content CC103" + _FILLER),
        _FakePage(
            "Curriculum Map for the Bachelor of Science in Information Systems\n"
            + _FILLER
            + " IS101"
        ),
        _FakePage("more IS content IS102" + _FILLER),
        _FakePage(
            "Curriculum Map for the Bachelor of Science in Information Technology\n"
            + _FILLER
            + " IT101"
        ),
        _FakePage("Section 11 Sample Means of Curriculum Delivery" + _FILLER),
        _FakePage("back matter after section 11" + _FILLER),
    ]


def test_includes_only_cs_and_it_sections_by_default(monkeypatch):
    _install_fake_fitz(monkeypatch, _cs_it_is_pages())

    records = extract_curriculum_map_courses("fake.pdf")

    assert [r.page_number for r in records] == [2, 3, 6, 7]
    assert all("information systems" not in r.course_title.lower() for r in records)


def test_section_end_marker_stops_inclusion(monkeypatch):
    _install_fake_fitz(monkeypatch, _cs_it_is_pages())

    records = extract_curriculum_map_courses("fake.pdf")

    # Page 8 (after "Section 11") must not be included even though no new
    # program header appears on it.
    assert 8 not in [r.page_number for r in records]


def test_custom_included_programs_narrows_selection(monkeypatch):
    _install_fake_fitz(monkeypatch, _cs_it_is_pages())

    records = extract_curriculum_map_courses(
        "fake.pdf", included_programs=("information systems",)
    )

    assert [r.page_number for r in records] == [4, 5]


def test_no_header_anywhere_returns_empty(monkeypatch):
    pages = [_FakePage("just some unrelated document text" + _FILLER)]
    _install_fake_fitz(monkeypatch, pages)

    records = extract_curriculum_map_courses("fake.pdf")

    assert records == []


def test_course_codes_collected_into_title(monkeypatch):
    _install_fake_fitz(monkeypatch, _cs_it_is_pages())

    records = extract_curriculum_map_courses("fake.pdf")

    cs_record = next(r for r in records if r.page_number == 2)
    assert "CC101" in cs_record.course_title
    assert "CC102" in cs_record.course_title


def test_selected_bscs_program_maps_to_cs_only_keyword():
    assert map_keywords_for_program("BSCS") == ("computer science",)
    assert map_keywords_for_program("bscs") == ("computer science",)


def test_selected_bsinfotech_program_maps_to_it_only_keyword():
    assert map_keywords_for_program("BSInfoTech") == ("information technology",)


def test_unrecognized_or_missing_program_falls_back_to_default():
    assert map_keywords_for_program("BSIS") == DEFAULT_INCLUDED_PROGRAMS
    assert map_keywords_for_program("BSChem") == DEFAULT_INCLUDED_PROGRAMS
    assert map_keywords_for_program(None) == DEFAULT_INCLUDED_PROGRAMS


def test_selected_program_narrows_map_extraction_to_that_program_only(monkeypatch):
    _install_fake_fitz(monkeypatch, _cs_it_is_pages())

    records = extract_curriculum_map_courses(
        "fake.pdf", included_programs=map_keywords_for_program("BSCS")
    )

    assert [r.page_number for r in records] == [2, 3]
