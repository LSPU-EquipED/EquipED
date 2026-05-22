from __future__ import annotations

from server.modules.documents.boilerplate import strip_repeated_page_boilerplate


def test_strip_repeated_page_boilerplate_removes_shared_header_and_footer() -> None:
    pages = [
        "LSPU SCC SLM\nProgram: BSIT\nPage 1 of 3\nDepartment of Computer Studies\n\nLearning outcomes include critical thinking.\n\nConfidential\nPrepared by LSPU",
        "LSPU SCC SLM\nProgram: BSIT\nPage 2 of 3\nDepartment of Computer Studies\n\nAssessment is 30% quiz and 70% exam.\n\nConfidential\nPrepared by LSPU",
        "LSPU SCC SLM\nProgram: BSIT\nPage 3 of 3\nDepartment of Computer Studies\n\nData privacy applies.\n\nConfidential\nPrepared by LSPU",
    ]

    cleaned = strip_repeated_page_boilerplate(pages)

    assert cleaned == [
        "Learning outcomes include critical thinking.",
        "Assessment is 30% quiz and 70% exam.",
        "Data privacy applies.",
    ]


def test_strip_repeated_page_boilerplate_keeps_non_repeated_content() -> None:
    pages = [
        "Course overview\n\nPage 1 content.",
        "Learning outcomes\n\nPage 2 content.",
        "Weekly topics\n\nPage 3 content.",
    ]

    cleaned = strip_repeated_page_boilerplate(pages)

    assert cleaned == [
        "Course overview\nPage 1 content.",
        "Learning outcomes\nPage 2 content.",
        "Weekly topics\nPage 3 content.",
    ]


def test_strip_repeated_page_boilerplate_keeps_distinct_front_matter() -> None:
    pages = [
        "Cover Page\nProgram: BSIT\n\nPage A content.",
        "Cover Page\nProgram: BSBA\n\nPage B content.",
        "Cover Page\nProgram: BSED\n\nPage C content.",
    ]

    cleaned = strip_repeated_page_boilerplate(pages)

    assert cleaned == [
        "Page A content.",
        "Page B content.",
        "Page C content.",
    ]


def test_strip_repeated_page_boilerplate_removes_varying_header_lines() -> None:
    pages = [
        "LSPU SCC SLM\nProgram: BSIT\nInstructor: Dela Cruz\nDepartment of Computer Studies\n\nUnit 1 lesson content.",
        "LSPU SCC SLM\nProgram: BSIT\nInstructor: Santos\nDepartment of Computer Studies\n\nUnit 2 lesson content.",
        "LSPU SCC SLM\nProgram: BSIT\nInstructor: Reyes\nDepartment of Computer Studies\n\nUnit 3 lesson content.",
    ]

    cleaned = strip_repeated_page_boilerplate(pages)

    assert cleaned == [
        "Unit 1 lesson content.",
        "Unit 2 lesson content.",
        "Unit 3 lesson content.",
    ]


def test_strip_repeated_page_boilerplate_removes_shifted_slm_header() -> None:
    pages = [
        "Intro text\n\nRepublic of the Philippines\nLaguna State Polytechnic University\nISO 9001:2015 Certified\nLevel I Institutionally Accredited\n\nPage 1 content.",
        "Intro text\n\nRepublic of the Philippines\nLaguna State Polytechnic University\nISO 9001:2015 Certified\nLevel I Institutionally Accredited\n\nPage 2 content.",
        "Intro text\n\nRepublic of the Philippines\nLaguna State Polytechnic University\nISO 9001:2015 Certified\nLevel I Institutionally Accredited\n\nPage 3 content.",
    ]

    cleaned = strip_repeated_page_boilerplate(pages)

    assert cleaned == [
        "Page 1 content.",
        "Page 2 content.",
        "Page 3 content.",
    ]


def test_strip_repeated_page_boilerplate_keeps_pages_without_footer() -> None:
    pages = [
        "Republic of the Philippines\nLaguna State Polytechnic University\nISO 9001:2015 Certified\nLevel I Institutionally Accredited\n\nFirst page body.",
        "Republic of the Philippines\nLaguna State Polytechnic University\nISO 9001:2015 Certified\nLevel I Institutionally Accredited\n\nSecond page body.",
        "Republic of the Philippines\nLaguna State Polytechnic University\nISO 9001:2015 Certified\nLevel I Institutionally Accredited\n\nThird page body.",
    ]

    cleaned = strip_repeated_page_boilerplate(pages)

    assert cleaned == [
        "First page body.",
        "Second page body.",
        "Third page body.",
    ]
