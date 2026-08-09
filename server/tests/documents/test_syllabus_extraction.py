import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from server.modules.documents.exceptions import ExtractionFailedError
from server.modules.documents.syllabus.extraction import (
    SyllabusCourseContentRecord,
    extract_syllabus_course_contents,
)


@dataclass
class PageText:
    page_number: int
    text: str = ""
    is_ocr: bool = False


class FakeTable:
    def __init__(
        self,
        matrix: list[list[str | None]],
        *,
        xs: tuple[float, ...] = (50, 140, 500, 560),
        y0: float = 100,
    ):
        self._matrix = matrix
        self.col_count = len(xs) - 1
        self.row_count = len(matrix)
        self.bbox = (xs[0], y0, xs[-1], y0 + 30 * len(matrix))
        self.rows = []
        for row_index in range(len(matrix)):
            top = y0 + 30 * row_index
            self.rows.append(
                SimpleNamespace(
                    cells=[
                        (xs[index], top, xs[index + 1], top + 30)
                        for index in range(self.col_count)
                    ]
                )
            )

    def extract(self):
        return self._matrix


class FakePage:
    def __init__(self, *tables: FakeTable):
        self._tables = list(tables)
        self.rect = SimpleNamespace(width=612.0)

    def find_tables(self):
        return SimpleNamespace(tables=self._tables)


class FakeDocument:
    is_encrypted = False

    def __init__(self, pages: list[FakePage]):
        self._pages = pages

    def __len__(self):
        return len(self._pages)

    def __iter__(self):
        return iter(self._pages)

    def __getitem__(self, index: int):
        return self._pages[index]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def _install_document(monkeypatch, pages: list[FakePage]) -> None:
    monkeypatch.setattr("fitz.open", lambda _path: FakeDocument(pages))
    monkeypatch.setattr(Path, "exists", lambda _path: True)


def test_extracts_course_contents_across_headerless_continuation_page(
    monkeypatch,
):
    pdf = "syllabus.pdf"
    _install_document(
        monkeypatch,
        [
            FakePage(
                FakeTable(
                    [
                        ["Week", "Course Contents", "Hours"],
                        ["1", "Foundations of networking", "3"],
                        ["2", "Network models and protocols", "3"],
                    ]
                )
            ),
            FakePage(
                FakeTable(
                    [
                        ["3", "Addressing and subnetting", "3"],
                        ["4", "Routing fundamentals", "3"],
                    ]
                )
            ),
        ],
    )

    records = extract_syllabus_course_contents(
        pdf,
        [PageText(1), PageText(2, is_ocr=True)],
    )

    assert [record.content for record in records] == [
        "Foundations of networking",
        "Network models and protocols",
        "Addressing and subnetting",
        "Routing fundamentals",
    ]
    assert [record.page_number for record in records] == [1, 1, 2, 2]
    assert [record.row_index for record in records] == [0, 1, 2, 3]
    assert [record.is_ocr for record in records] == [False, False, True, True]


def test_skips_a_repeated_header_when_present(monkeypatch):
    pdf = "syllabus.pdf"
    _install_document(
        monkeypatch,
        [
            FakePage(
                FakeTable(
                    [
                        ["Week", "Course Contents", "Hours"],
                        ["1", "First topic", "3"],
                    ]
                )
            ),
            FakePage(
                FakeTable(
                    [
                        ["Week", "Course Contents", "Hours"],
                        ["2", "Second topic", "3"],
                    ]
                )
            ),
        ],
    )

    records = extract_syllabus_course_contents(pdf, [PageText(1), PageText(2)])

    assert [record.content for record in records] == ["First topic", "Second topic"]


def test_stops_at_first_page_without_matching_table_geometry(monkeypatch):
    pdf = "syllabus.pdf"
    matching = (50, 140, 500, 560)
    different = (20, 200, 400, 590)
    _install_document(
        monkeypatch,
        [
            FakePage(
                FakeTable(
                    [["Week", "Course Contents", "Hours"], ["1", "Included", "3"]],
                    xs=matching,
                )
            ),
            FakePage(FakeTable([["A", "Unrelated", "B"]], xs=different)),
            FakePage(FakeTable([["2", "Must not resume", "3"]], xs=matching)),
        ],
    )

    records = extract_syllabus_course_contents(
        pdf, [PageText(1), PageText(2), PageText(3)]
    )

    assert [record.content for record in records] == ["Included"]


def test_fails_closed_when_course_contents_table_is_missing(monkeypatch):
    pdf = "syllabus.pdf"
    _install_document(
        monkeypatch,
        [FakePage(FakeTable([["Week", "Topic", "Hours"], ["1", "Intro", "3"]]))],
    )

    with pytest.raises(ExtractionFailedError, match="No table"):
        extract_syllabus_course_contents(pdf, [PageText(1)])


def test_fails_closed_for_multiple_course_contents_tables(monkeypatch):
    pdf = "syllabus.pdf"
    table = [["Week", "Course Contents", "Hours"], ["1", "Topic", "3"]]
    _install_document(monkeypatch, [FakePage(FakeTable(table), FakeTable(table))])

    with pytest.raises(ExtractionFailedError, match="Multiple ambiguous"):
        extract_syllabus_course_contents(pdf, [PageText(1)])


def test_ingestion_emits_only_course_content_chunks(monkeypatch):
    from server.modules.documents.ingestion.pipeline import (
        _ingest_syllabus_course_contents,
    )

    monkeypatch.setattr(
        "server.modules.documents.syllabus.extraction.extract_syllabus_course_contents",
        lambda _file_path, _pages: [
            SyllabusCourseContentRecord(
                content="Network models and routing fundamentals.",
                page_number=4,
                row_index=0,
                is_ocr=False,
            )
        ],
    )

    chunks = _ingest_syllabus_course_contents(
        "syllabus.pdf", [PageText(4)], "all", uuid.uuid4()
    )

    assert [chunk.text for chunk in chunks] == [
        "Network models and routing fundamentals."
    ]
    assert chunks[0].section_ref == "syllabus_course_content:1:1"
    assert chunks[0].page_number == 4
