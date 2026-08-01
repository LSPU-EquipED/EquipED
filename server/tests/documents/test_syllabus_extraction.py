from dataclasses import dataclass

import pytest
from server.modules.documents.exceptions import ExtractionFailedError
from server.modules.documents.syllabus_extraction import extract_syllabus_outcomes


@dataclass
class Page:
    page_number: int
    text: str
    is_ocr: bool = False


def test_extracts_only_ordered_outcome_rows_with_provenance():
    pages = [
        Page(1, "Institution header\nUnrelated course description"),
        Page(
            2,
            """Course Learning Outcomes
Code | Outcome Description
CLO1 | Explain core networking concepts and terminology.
CLO2 | Configure a secure local area network
using appropriate devices and protocols.
Assessment
Quizzes and laboratory work
""",
            True,
        ),
    ]

    outcomes = extract_syllabus_outcomes(pages)

    assert [(item.code, item.page_number, item.row_index) for item in outcomes] == [
        ("CLO1", 2, 0),
        ("CLO2", 2, 1),
    ]
    assert outcomes[1].description == (
        "Configure a secure local area network using appropriate devices and protocols."
    )
    assert all(item.is_ocr for item in outcomes)
    assert "Institution header" not in " ".join(item.description for item in outcomes)


@pytest.mark.parametrize(
    "text",
    [
        "Course description only",
        "Course Outcomes\nCLO1 Explain networking concepts.",
        "Course Outcomes\nCode | Outcome Description\n",
    ],
)
def test_fails_closed_for_missing_or_malformed_table(text):
    with pytest.raises(ExtractionFailedError):
        extract_syllabus_outcomes([Page(1, text)])


def test_rejects_duplicate_outcome_codes():
    with pytest.raises(ExtractionFailedError, match="duplicate"):
        extract_syllabus_outcomes(
            [
                Page(
                    1,
                    "Course Outcomes\nCode | Outcome Description\n"
                    "CO1 Explain foundational course concepts.\n"
                    "CO1 Apply foundational course concepts correctly.\n",
                )
            ]
        )


def test_supports_cell_text_extracted_on_separate_lines():
    outcomes = extract_syllabus_outcomes(
        [
            Page(
                1,
                "Course Outcomes\nCode\nOutcome Description\n"
                "CO1\nExplain foundational networking concepts.\n"
                "CO2\nConfigure a secure local area network.\nAssessment\n",
            )
        ]
    )
    assert [item.code for item in outcomes] == ["CO1", "CO2"]
