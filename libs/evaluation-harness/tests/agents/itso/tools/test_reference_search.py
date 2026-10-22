import asyncio
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from equiped_harness.agents.itso.execution import AgentExecutionError, _references
from equiped_harness.agents.itso.tools.contracts import (
    Code,
    VerificationError,
)
from equiped_harness.agents.itso.tools.reference_search import (
    NoQueryableReferencesError,
    ReferenceToolsUnavailable,
    build_public_reference_report,
    extract_bibliography,
    extract_public_topics,
    readiness_config,
)
from equiped_harness.tools.http import Response


class Settings:
    enabled = True


DDG_EMPTY = b'<html><body><div class="no-results">No results found</div></body></html>'


def ddg_result(title="A Useful Study", url="https://example.org/study"):
    href = "https://html.duckduckgo.com/l/?" + urlencode({"uddg": url})
    return (
        '<html><body><div class="result">'
        f'<a class="result__a" href="{href}">{title}</a>'
        "</div></body></html>"
    ).encode()


def ddg_results(*results):
    links = "".join(
        '<a class="result__a" href="https://html.duckduckgo.com/l/?'
        + urlencode({"uddg": url})
        + f'">{title}</a>'
        for title, url in results
    )
    return f"<html><body>{links}</body></html>".encode()


class FakeTransport:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    async def get(self, request, deadline):
        self.requests.append(request)
        if request.url in self.responses:
            response = self.responses[request.url]
            if isinstance(response, Exception):
                raise response
            return response
        if "crossref" in request.url:
            return Response(404, {}, b"")
        if "datacite" in request.url:
            return Response(404, {}, b"")
        if request.kind == "duckduckgo":
            return self.responses["duckduckgo"]
        return Response(404, {}, b"")


def test_extracts_only_explicit_bibliography_and_bounds_queries():
    source = (
        "References\n[1] Ada Author (2022). A Useful Study. "
        "https://doi.org/10.1234/example\n"
        "Assessment\nPrivate student record must never be queried\n"
    )
    found = extract_bibliography(source)
    assert len(found) == 1
    assert "Private student" not in found[0].query
    assert found[0].reference.doi == "10.1234/example"
    assert extract_bibliography("A useful reference appears in this SLM body.") == ()


@pytest.mark.parametrize(
    ("section", "citation", "expected_title"),
    [
        (
            "References\n",
            "Ada Author (2022). A Useful Study.",
            "A Useful Study",
        ),
        (
            "Learning Resources\n",
            "1. Dix, Alan. Human Computer Interaction. 2007.",
            "Human Computer Interaction",
        ),
    ],
)
def test_heading_search_finds_references_after_long_body(
    section, citation, expected_title
):
    source = "Ordinary SLM body text.\n" * 600 + section + citation
    found = extract_bibliography(source)
    assert len(found) == 1
    assert found[0].reference.title == expected_title


def test_extracts_flattened_learning_resources_as_cited_work_metadata():
    source = (
        "Learning Resources 1. Sears, Andrew and Jacko Julie A. (Eds). Human "
        "Computer Interaction Fundamentals. CRC Press, Taylor and Francis "
        "Group. 2009. 2. Dix, Alan, Finlay, Janet, Abowd, Gregory, and Beale, "
        "Russell. Human-Computer Interaction. 3rd Edition 2007. 3. Preece, "
        "Jenny. Human Computer Interaction 4. Shneiderman, Ben. Designing "
        "the User Interface Ben 3rd Edition 2008."
    )
    found = extract_bibliography(source)
    assert [item.reference.title for item in found] == [
        "Human Computer Interaction Fundamentals",
        "Human-Computer Interaction",
        "Human Computer Interaction",
        "Designing the User Interface Ben",
    ]
    assert found[0].citation_section == "learning_resources"
    assert found[0].reference.authors
    assert found[2].reference.year is None


def test_extracts_flattened_apa_learning_resources_including_corporate_authors():
    source = (
        "Learning Resources 1. Dix, A., Finlay, J., Abowd, G., & Beale, R. "
        "(n.d.). Human–computer interaction (Chapter 1). Retrieved from hcibook.com. "
        "2. Evident Scientific. (n.d.). Human vision & color perception: How the eye "
        "processes light. Retrieved from https://evidentscientific.com. "
        "3. StatPearls Publishing. (2025). Physiology, color perception. "
        "NCBI Bookshelf. "
        "4. Interaction Design Foundation. (2017). What is color in UX design? "
        "Retrieved from https://ixdf.org. "
        "5. Interaction Design Foundation. (2023). UI color palette 2026: "
        "Best practices, tips, and tricks for designers. "
        "6. Full Clarity. (2024). Colour theory for UI design: "
        "UX UI colour best practice guide. "
        "7. Material Design. (n.d.). Applying color to UI. "
        "Retrieved from https://m2.material.io. "
        "8. Studocu. (2023). Input–output channels in "
        "human–computer interaction (HCI). "
        "9. Scribd. (2025). Human input–output channels in HCI "
        "(Unit 1 exam prep notes). "
        "10. NCBI / various authors. (2019). Brightness–color interactions "
        "in human early visual cortex and related works on color–brightness "
        "interaction.\n"
        "Prepared by PRIVATE PERSON"
    )
    found = extract_bibliography(source)
    assert len(found) == 10
    assert [item.reference.year for item in found] == [
        None,
        None,
        2025,
        2017,
        2023,
        2024,
        None,
        2023,
        2025,
        2019,
    ]
    assert found[0].reference.title.startswith("Human–computer interaction")
    assert found[1].reference.title.startswith("Human vision & color perception")
    assert found[3].reference.title == "What is color in UX design?"
    assert found[4].reference.title.startswith("UI color palette 2026")
    assert found[1].reference.authors == ("Evident Scientific",)
    assert found[2].reference.authors == ("StatPearls Publishing",)
    assert found[9].reference.authors == ("NCBI / various authors",)
    assert all("Prepared" not in item.query for item in found)


def test_standard_references_accepts_apa_no_date_without_year_from_title():
    found = extract_bibliography(
        "References\n"
        "Material Design. (n.d.). UI color palette 2026: Applying color to UI.\n"
    )
    assert len(found) == 1
    assert found[0].reference.authors == ("Material Design",)
    assert found[0].reference.year is None
    assert found[0].reference.title == "UI color palette 2026: Applying color to UI"


def test_apa_spaced_no_date_is_normalized_without_year_conversion():
    found = extract_bibliography("References\nNamed Author. (n. d.). A Useful Work.\n")
    assert len(found) == 1
    assert found[0].reference.year is None
    assert found[0].reference.title == "A Useful Work"


@pytest.mark.parametrize(
    "citation",
    [
        "Private Person. (n.d.).",
        "Student ID. (2024). Prepared by.",
        "Named Author. (n.d.). (n.d.).",
    ],
)
def test_apa_placeholder_or_private_metadata_is_never_a_query(citation):
    assert extract_bibliography(f"Learning Resources 1. {citation}") == ()


@pytest.mark.parametrize("heading", ["Learning Resources 1.", "References\n[1]"])
@pytest.mark.parametrize("label", ["ID No.", "ID Number"])
def test_apa_author_identifiers_are_never_public_queries(heading, label):
    source = f"{heading} Doe, Jane, {label} 20240001. (n.d.). A Useful Work."
    assert extract_bibliography(source) == ()


@pytest.mark.parametrize("heading", ["Learning Resources 1.", "References\n[1]"])
@pytest.mark.parametrize("title", ["What is color in UX design?", "Design for color!"])
@pytest.mark.parametrize(
    "suffix", ["Retrieved from https://ixdf.org.", "Scientific American."]
)
def test_apa_question_and_exclamation_titles_exclude_citation_suffixes(
    heading, title, suffix
):
    found = extract_bibliography(
        f"{heading} Interaction Design Foundation. (2017). {title} {suffix}"
    )
    assert len(found) == 1
    assert found[0].reference.title == title
    assert "Retrieved" not in found[0].query


@pytest.mark.parametrize("title", ["(n.d.)", "(2025)", "2025", "Retrieved from"])
def test_apa_metadata_alone_is_not_a_work_title(title):
    assert (
        extract_bibliography(f"Learning Resources 1. Named Author. (n.d.). {title}.")
        == ()
    )


def test_learning_resources_multiline_stops_at_next_heading_even_if_apa_like():
    source = (
        "Learning Resources\n"
        "1. Dix, Alan, Finlay, Janet, Abowd, Gregory, and Beale, Russell. "
        "Human-Computer Interaction. 3rd Edition 2007.\n"
        "Prepared by\n"
        "Private Person (2021). Private Student Record.\n"
    )
    found = extract_bibliography(source)
    assert len(found) == 1
    assert found[0].reference.title == "Human-Computer Interaction"
    assert "Private" not in found[0].query


def test_learning_resources_skips_entries_without_identifiable_author_and_work():
    source = (
        "Learning Resources\n"
        "1. Vincent Aleven. Human Computer Interaction Institute (HCII), "
        "United States, Pennsylvania, Pittsburgh 2010.\n"
        "2. Smith-Atakan. 2006.\n"
    )
    assert extract_bibliography(source) == ()


def test_learning_resources_phrase_in_prose_is_not_a_section_heading():
    source = (
        "Learning Resources are useful for this unit. 1. Ada Author. "
        "A Useful Study. 2022."
    )
    assert extract_bibliography(source) == ()


@pytest.mark.parametrize(
    "source",
    [
        "Learning Resources 1. Dix, Alan. Human Computer Interaction. 2007. "
        "Prepared by 2. Doe, Jane. Confidential Narrative. 2024.",
        "Learning Resources\n"
        "1. Dix, Alan. Human Computer Interaction. 2007.\n"
        "Prepared by 2. Doe, Jane. Confidential Narrative. 2024.",
        "Learning Resources\n"
        "1. Dix, Alan. Human Computer Interaction. 2007.\n"
        "Additional private discussion follows.\n"
        "2. Doe, Jane. Confidential Narrative. 2024.",
    ],
)
def test_learning_resources_never_searches_citations_after_private_or_prose_boundary(
    source,
):
    transport = FakeTransport({"duckduckgo": Response(200, {}, DDG_EMPTY)})
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    requests = [req for req in transport.requests if req.kind == "duckduckgo"]
    queries = [parse_qs(urlparse(req.url).query)["q"][0] for req in requests]
    assert len(queries) == 2
    assert all("Human Computer Interaction" in query for query in queries)
    assert all(
        value not in query
        for query in queries
        for value in ("Prepared", "Doe", "Jane", "Confidential", "Narrative", "2024")
    )
    assert len(report["references"]) == 1


def test_learning_resources_report_searches_named_works_and_reports_citation():
    source = (
        "Learning Resources 1. Sears, Andrew and Jacko Julie A. (Eds). "
        "Human Computer Interaction Fundamentals. CRC Press. 2009."
    )
    transport = FakeTransport({"duckduckgo": Response(200, {}, DDG_EMPTY)})
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    request = next(req for req in transport.requests if req.kind == "duckduckgo")
    query = parse_qs(urlparse(request.url).query)["q"][0]
    assert "Human Computer Interaction Fundamentals" in query
    assert "Sears" in query and "2009" in query
    assert report["bibliography_status"] == "found"
    assert report["reference_sections"] == ["learning_resources"]
    assert report["references"][0]["cited_reference"] == {
        "section": "learning_resources",
        "title": "Human Computer Interaction Fundamentals",
        "authors": ["Sears, Andrew and Jacko Julie A. (Eds)"],
        "year": 2009,
        "doi": None,
    }
    citation = report["references"][0]["cited_reference"]
    assert len(citation["title"]) <= 300
    assert len(citation["authors"]) <= 8
    assert all(len(author) <= 100 for author in citation["authors"])
    assert report["references"][0]["status"] == "unverified"


def test_learning_resources_title_only_page_match_keeps_authors_and_year_ambiguous():
    source = (
        "Learning Resources 1. Sears, Andrew and Jacko Julie A. (Eds). "
        "Human Computer Interaction Fundamentals. CRC Press. 2009."
    )
    page = (
        b"<html><head><title>Human Computer Interaction Fundamentals</title>"
        b"</head><body><p>Human computer interaction fundamentals describe "
        b"a complete set of principles for designing interactive systems "
        b"and evaluating their usability.</p></body></html>"
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200, {}, ddg_result("Human Computer Interaction Fundamentals")
            ),
            "https://example.org/study": Response(200, {}, page),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    row = report["references"][0]
    assert row["status"] == "ambiguous"
    assert row["matched_fields"] == ["page_title"]
    assert row["unverified_fields"] == ["author", "year"]
    assert row["cited_reference"]["authors"] == [
        "Sears, Andrew and Jacko Julie A. (Eds)"
    ]
    assert row["cited_reference"]["year"] == 2009


def test_disabled_report_does_no_transport_io():
    transport = FakeTransport({})
    report = asyncio.run(
        build_public_reference_report(
            "References\nA (2020). A title",
            enabled=False,
            settings=Settings(),
            transport=transport,
        )
    )
    assert report["status"] == "disabled"
    assert transport.requests == []


def test_enabled_report_without_queryable_bibliography_fails_before_io():
    transport = FakeTransport({})
    with pytest.raises(
        NoQueryableReferencesError,
        match="No safely queryable public bibliography references or labelled",
    ):
        asyncio.run(
            build_public_reference_report(
                "Private SLM body with no bibliography",
                enabled=True,
                settings=Settings(),
                transport=transport,
            )
        )
    assert transport.requests == []


def test_extracts_only_bounded_explicit_public_topic_fields():
    text = (
        "Course CMSC 313- HUMAN COMPUTER INTERACTION Sem/AY 2025-2026 "
        "Module No. 4 Lesson Title HUMAN INPUT-OUTPUT CHANNELS "
        "Week Duration Week 8-9 Date October 2026 "
        "Description of the Lesson This lesson discusses student records."
    )
    topics = extract_public_topics(text)
    assert len(topics) == 1
    assert topics[0].query == "HUMAN INPUT-OUTPUT CHANNELS"
    assert topics[0].query_kind == "topic"


def test_topic_in_assessment_body_does_not_become_an_additional_search_query():
    text = (
        "Lesson Title HUMAN INPUT-OUTPUT CHANNELS Week Duration Week 8-9 "
        "Description of the Lesson: Course content. Assessment: Topic: "
        "Jane Doe student record and private identifier 123456."
    )
    topics = extract_public_topics(text)
    assert len(topics) == 1
    assert topics[0].query == "HUMAN INPUT-OUTPUT CHANNELS"


def test_identity_field_after_lesson_title_is_never_in_search_query():
    source = (
        "Lesson Title: Human Computer Interaction Name: Jane Doe "
        "Description: Introductory material."
    )
    transport = FakeTransport({"duckduckgo": Response(200, {}, DDG_EMPTY)})
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    request = next(
        request for request in transport.requests if request.kind == "duckduckgo"
    )
    query = parse_qs(urlparse(request.url).query)["q"][0]
    assert query == "Human Computer Interaction"
    assert "Jane" not in query and "Doe" not in query
    assert report["references"][0]["query"] == "Human Computer Interaction"


def test_inline_topic_in_discussion_body_does_not_trigger_search_io():
    source = (
        "Module text\nDiscussion\n"
        "This case describes the Topic: Jane Doe medical history."
    )
    transport = FakeTransport({})
    with pytest.raises(NoQueryableReferencesError):
        asyncio.run(
            build_public_reference_report(
                source, enabled=True, settings=Settings(), transport=transport
            )
        )
    assert transport.requests == []


@pytest.mark.parametrize(
    "text",
    [
        "A useful lesson explains data privacy without a labelled topic field.",
        "The Topic NAME appears in this ordinary paragraph before the description.",
        "Topic: Student Name Jane Doe, email jane@example.org",
        "Lesson Title: Student ID 123456 and personal phone 09171234567",
        "Unit: October 20, 2026",
    ],
)
def test_private_or_unlabelled_text_does_not_become_a_topic_query(text):
    assert extract_public_topics(text) == ()


def test_search_browse_extracts_real_page_context_and_matches_title():
    source = "References\n[1] Ada Author (2022). A Useful Study. Journal."
    html = (
        b"<html><head><title>A Useful Study</title>"
        b"<meta name='author' content='Ada Author'></head><body>"
        b"<nav>A Useful Study</nav><p>This study examines useful findings in detail. "
        b"The useful study reports a reproducible analysis across multiple sites.</p>"
        b"</body></html>"
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(200, {}, ddg_result()),
            "https://example.org/study": Response(
                200, {"content-type": "text/html"}, html
            ),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    assert report["status"] == "completed"
    assert report["references"][0]["status"] == "matched"
    assert report["references"][0]["source_url"] == "https://example.org/study"
    assert "This study examines" in report["references"][0]["excerpt"]
    assert any(req.kind == "document" for req in transport.requests)
    assert report["provider"] == "duckduckgo_html"
    assert report["attempts"] == {"search": 1, "source": 1}


def test_no_bibliography_searches_only_lesson_name_and_reports_topic_context():
    source = (
        "Course CMSC 313- HUMAN COMPUTER INTERACTION Sem/AY 2025-2026 "
        "Module No. 4 Lesson Title HUMAN INPUT-OUTPUT CHANNELS "
        "Week Duration Week 8-9 Date October 2026 "
        "Description of the Lesson This lesson discusses student records for "
        "Jane Doe, ID 123456, jane@example.org."
    )
    page = (
        b"<html><head><title>Human Input-Output Channels</title></head><body><p>"
        b"Human input-output channels describe the methods people use to"
        b" communicate with interactive computing systems and interfaces.</p>"
        b"</body></html>"
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(200, {}, ddg_result("Human Input-Output Channels")),
            "https://example.org/study": Response(200, {}, page),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    search_request = next(
        request for request in transport.requests if request.kind == "duckduckgo"
    )
    query = parse_qs(urlparse(search_request.url).query)["q"][0]
    row = report["references"][0]
    assert query == "HUMAN INPUT-OUTPUT CHANNELS"
    assert all(
        value not in query for value in ("CMSC", "2025", "Jane", "123456", "jane")
    )
    assert report["bibliography_status"] == "not_detected"
    assert report["coverage"]["found"] == 0
    assert report["coverage"]["topic_queries"] == {
        "found": 1,
        "checked": 1,
        "skipped": 0,
        "total": 1,
    }
    assert row["query_kind"] == "topic"
    assert row["bibliography_status"] == "not_detected"
    assert row["status"] == "matched"
    assert row["matched_fields"] == ["topic"]
    assert row["registry_status"] == "not_applicable"
    assert row["source_url"] == "https://example.org/study"
    assert row["excerpt"] is not None


def test_breadcrumb_and_heading_text_alone_cannot_match_a_topic_source():
    source = (
        "Lesson Title HUMAN INPUT-OUTPUT CHANNELS Week Duration Week 8-9 Description"
    )
    html = (
        "<html><head><title>Human Input-Output Channels</title></head><body>"
        '<nav aria-label="Breadcrumb">Home » Computers » '
        "Human Input-Output Channels</nav>"
        "<h1>Human Input-Output Channels</h1>"
        "</body></html>"
    ).encode()
    transport = FakeTransport(
        {
            "duckduckgo": Response(200, {}, ddg_result("Human Input-Output Channels")),
            "https://example.org/study": Response(200, {}, html),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    result = report["references"][0]
    assert result["status"] == "unverified"
    assert result["excerpt"] is None


def test_breadcrumb_is_excluded_when_real_source_paragraph_is_available():
    source = (
        "Lesson Title HUMAN INPUT-OUTPUT CHANNELS Week Duration Week 8-9 Description"
    )
    html = (
        "<html><head><title>Human Input-Output Channels</title></head><body>"
        '<div class="breadcrumb">Home » Computers » '
        "Human Input-Output Channels</div>"
        "<h1>Human Input-Output Channels</h1><main><p>"
        "Human input-output channels describe the methods people use to"
        " communicate with interactive computing systems and interfaces.</p></main>"
        "</body></html>"
    ).encode()
    transport = FakeTransport(
        {
            "duckduckgo": Response(200, {}, ddg_result("Human Input-Output Channels")),
            "https://example.org/study": Response(200, {}, html),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    result = report["references"][0]
    assert result["status"] == "matched"
    assert result["excerpt"] == (
        "Human input-output channels describe the methods people use to "
        "communicate with interactive computing systems and interfaces."
    )
    assert "Home" not in result["excerpt"]


def test_topic_fallback_keeps_no_query_failure_for_private_malformed_heading():
    text = "Topic: Student Name Jane Doe, email jane@example.org"
    transport = FakeTransport({})
    with pytest.raises(NoQueryableReferencesError):
        asyncio.run(
            build_public_reference_report(
                text, enabled=True, settings=Settings(), transport=transport
            )
        )
    assert transport.requests == []


def test_search_inspects_bounded_candidates_until_a_real_page_match():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    html = (
        b"<html><head><title>A Useful Study</title></head><body><p>"
        b"This useful study reports detailed findings and methods from a"
        b" reproducible analysis at multiple sites.</p></body></html>"
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200,
                {},
                ddg_results(
                    ("A Useful Study", "https://example.org/broken"),
                    ("A Useful Study", "https://example.org/study"),
                    ("A Useful Study", "https://example.org/unused"),
                ),
            ),
            "https://example.org/broken": Response(503, {}, b""),
            "https://example.org/study": Response(200, {}, html),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    assert report["references"][0]["status"] == "matched"
    assert report["references"][0]["source_url"] == "https://example.org/study"
    assert report["attempts"] == {"search": 1, "source": 3}
    assert "https://example.org/unused" not in [
        request.url for request in transport.requests
    ]


def test_malformed_source_does_not_block_a_later_real_candidate_match():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    page = (
        b"<html><head><title>A Useful Study</title></head><body><p>"
        b"This useful study reports detailed findings and methods from a"
        b" reproducible analysis at multiple sites.</p></body></html>"
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200,
                {},
                ddg_results(
                    ("A Useful Study", "https://example.org/malformed"),
                    ("A Useful Study", "https://example.org/study"),
                ),
            ),
            "https://example.org/malformed": VerificationError(Code.MALFORMED),
            "https://example.org/study": Response(200, {}, page),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    result = report["references"][0]
    assert report["attempts"] == {"search": 1, "source": 2}
    assert result["status"] == "matched"
    assert result["source_url"] == "https://example.org/study"
    assert result["excerpt"] is not None


def test_all_malformed_source_candidates_remain_unverified_without_fake_excerpt():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200,
                {},
                ddg_results(
                    ("A Useful Study", "https://example.org/one"),
                    ("A Useful Study", "https://example.org/two"),
                ),
            ),
            "https://example.org/one": VerificationError(Code.MALFORMED),
            "https://example.org/two": VerificationError(Code.LIMIT),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    result = report["references"][0]
    assert report["attempts"] == {"search": 2, "source": 2}
    assert result["status"] == "unavailable"
    assert result["source_url"] is None
    assert result["excerpt"] is None


def test_source_redirects_are_bounded_and_destination_is_validated():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    page = (
        b"<html><head><title>A Useful Study</title></head><body><p>"
        b"This useful study reports detailed findings and methods from a"
        b" reproducible analysis at multiple sites.</p></body></html>"
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(200, {}, ddg_result()),
            "https://example.org/study": Response(302, {"location": "../final"}, b""),
            "https://example.org/final": Response(200, {}, page),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    assert report["references"][0]["source_url"] == "https://example.org/final"
    assert report["attempts"] == {"search": 1, "source": 2}
    attempt = report["references"][0]["source_attempts"][0]
    assert attempt["candidate_host"] == "example.org"
    assert attempt["candidate_url_hash"] != attempt["validated_url_hash"]
    assert attempt["validated_host"] == "example.org"
    assert attempt["outcome"] == "matched"


def test_source_redirect_limit_is_recorded_without_following_third_redirect():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    transport = FakeTransport(
        {
            "duckduckgo": Response(200, {}, ddg_result()),
            "https://example.org/study": Response(302, {"location": "/second"}, b""),
            "https://example.org/second": Response(302, {"location": "/third"}, b""),
            "https://example.org/third": Response(302, {"location": "/fourth"}, b""),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    attempt = report["references"][0]["source_attempts"][0]
    assert attempt["reason"] == "redirect_limit"
    assert attempt["http_status"] == 302
    assert "https://example.org/fourth" not in [
        request.url for request in transport.requests
    ]


def test_source_redirect_to_private_destination_is_skipped_without_aborting():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    transport = FakeTransport(
        {
            "duckduckgo": Response(200, {}, ddg_result()),
            "https://example.org/study": Response(
                302, {"location": "https://127.0.0.1/private"}, b""
            ),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    assert report["references"][0]["status"] == "unavailable"
    assert all("127.0.0.1" not in request.url for request in transport.requests)


def test_unsafe_source_candidate_is_skipped_for_later_real_page():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    page = (
        b"<html><head><title>A Useful Study</title></head><body><p>"
        b"This useful study reports detailed findings and methods from a"
        b" reproducible analysis at multiple sites.</p></body></html>"
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200,
                {},
                ddg_results(
                    ("A Useful Study", "https://example.org/unsafe"),
                    ("A Useful Study", "https://example.org/study"),
                ),
            ),
            "https://example.org/unsafe": Response(
                302, {"location": "https://127.0.0.1/private"}, b""
            ),
            "https://example.org/study": Response(200, {}, page),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    assert report["references"][0]["status"] == "matched"
    assert report["references"][0]["source_url"] == "https://example.org/study"
    assert all("127.0.0.1" not in request.url for request in transport.requests)


def test_blocked_source_is_unavailable_and_no_fake_match():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    transport = FakeTransport(
        {
            "duckduckgo": Response(200, {}, ddg_result()),
            "https://example.org/study": Response(403, {}, b""),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    assert report["references"][0]["status"] == "unavailable"
    assert report["references"][0]["excerpt"] is None
    attempt = report["references"][0]["source_attempts"][0]
    assert attempt["reason"] == "http_error"
    assert attempt["http_status"] == 403
    with pytest.raises(AgentExecutionError, match="usable public reference passage"):
        _references(
            SimpleNamespace(
                precomputed_context={
                    "public_reference_verification": (json.dumps(report),)
                },
                form_snapshot=SimpleNamespace(adapter_version=3),
            )
        )


def test_search_tries_through_fifth_candidate_and_stops_after_match():
    source = "Lesson Title: Introduction to Human Computer Interaction"
    matching_page = (
        b"<html><head><title>Introduction to Human Computer Interaction</title>"
        b"</head><body><p>Introduction to Human Computer Interaction explains "
        b"the principles and methods used to design interactive systems for "
        b"people in practical and research settings.</p></body></html>"
    )
    urls = [f"https://example.org/candidate-{index}" for index in range(1, 6)]
    responses = {
        "duckduckgo": Response(
            200,
            {},
            ddg_results(
                *(("Introduction to Human Computer Interaction", url) for url in urls)
            ),
        ),
        urls[0]: Response(403, {}, b""),
        urls[1]: Response(404, {}, b""),
        urls[2]: Response(503, {}, b""),
        urls[3]: Response(200, {}, matching_page),
    }
    transport = FakeTransport(responses)
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    row = report["references"][0]
    assert row["status"] == "matched"
    assert row["source_url"] == urls[3]
    assert len(row["source_attempts"]) == 4
    assert [attempt["http_status"] for attempt in row["source_attempts"]] == [
        403,
        404,
        503,
        200,
    ]
    assert [
        request.url for request in transport.requests if request.kind == "document"
    ] == [*urls[:3], urls[2], urls[3]]


def test_all_source_candidates_unavailable_leave_no_excerpt_or_private_errors():
    source = "Lesson Title: Introduction to Human Computer Interaction"
    urls = [f"https://example.org/candidate-{index}" for index in range(1, 4)]
    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200,
                {},
                ddg_results(
                    *(
                        ("Introduction to Human Computer Interaction", url)
                        for url in urls
                    )
                ),
            ),
            urls[0]: Response(403, {}, b"private response body"),
            urls[1]: Response(404, {}, b"private response body"),
            urls[2]: Response(503, {}, b"private response body"),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    row = report["references"][0]
    assert row["status"] == "unavailable"
    assert row["excerpt"] is None
    assert [attempt["reason"] for attempt in row["source_attempts"]] == [
        "http_error",
        "http_error",
        "http_error",
    ]
    encoded = json.dumps(report)
    assert "private response body" not in encoded
    assert "private" not in encoded


def test_long_source_attempt_diagnostics_compact_before_worker_report_limit():
    title = "A Useful Study " + "Useful " * 39
    title = title.rstrip()[:298]
    doi = "10.1234/" + "a" * 170
    source = "References\n" + "\n".join(
        f"[{index}] Ada Author (2022). {title}. https://doi.org/{doi}"
        for index in range(1, 6)
    )
    prefix = "https://example.org/"
    urls = [prefix + ("x" * (2047 - len(prefix))) + str(index) for index in range(1, 6)]
    page_text = (
        "This useful study describes detailed findings and methods from a "
        "reproducible analysis at multiple sites. "
    )
    paragraph = (page_text * 30)[:699] + "."
    page = (
        f"<html><head><title>{title}</title></head><body><p>"
        + paragraph
        + "</p></body></html>"
    ).encode()
    transport = FakeTransport(
        {
            "https://api.crossref.org/works/" + doi.replace("/", "%2F"): Response(
                200,
                {},
                json.dumps(
                    {
                        "status": "ok",
                        "message-type": "work",
                        "message": {
                            "title": [title],
                            "DOI": doi,
                            "author": [{"given": "Ada", "family": "Author"}],
                            "published": {"date-parts": [[2022]]},
                        },
                    }
                ).encode(),
            ),
            "duckduckgo": Response(
                200,
                {},
                ddg_results(*((title, url) for url in urls)),
            ),
            **{
                **{url: Response(403, {}, b"") for url in urls[:4]},
                urls[4]: Response(200, {}, page),
            },
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    encoded = json.dumps(report)
    assert report["source_attempt_identities_omitted"] is True
    assert report["source_attempt_details_omitted"] is True
    assert len(encoded) <= 24_000
    assert len(report["references"]) == 5
    assert all(row["status"] == "matched" for row in report["references"])
    assert all(row["source_url"] == urls[4] for row in report["references"])
    assert all(len(row["excerpt"]) == 700 for row in report["references"])
    assert all(
        sorted(
            (item["reason"], item["count"]) for item in row["source_attempt_summary"]
        )
        == [("http_error", 4), ("matched", 1)]
        for row in report["references"]
    )
    assert _references(
        SimpleNamespace(
            precomputed_context={"public_reference_verification": (encoded,)},
            form_snapshot=SimpleNamespace(adapter_version=3),
        )
    ) == [encoded]


def test_private_search_result_is_never_fetched():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    transport = FakeTransport(
        {"duckduckgo": Response(200, {}, ddg_result(url="https://127.0.0.1/private"))}
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    assert report["references"][0]["status"] == "unverified"
    assert all(request.kind != "document" for request in transport.requests)


def test_empty_search_result_is_unverified_with_explicit_coverage():
    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200,
                {},
                DDG_EMPTY,
            )
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=transport,
        )
    )
    assert report["status"] == "completed"
    assert report["references"][0]["status"] == "unverified"
    assert report["coverage"] == {"found": 1, "checked": 1, "skipped": 0, "total": 1}


def test_plain_section_heading_stops_bibliography_before_private_body():
    text = (
        "References\n[1] Ada Author (2022). A Useful Study.\n"
        "Appendix\nStudent ID 12345 and confidential assessment notes"
    )
    found = extract_bibliography(text)
    assert len(found) == 1
    assert "Student ID" not in found[0].query


@pytest.mark.parametrize(
    "section_heading",
    ["Answer Key", "Confidential Notes", "3. Answer Key", "Journal Notes"],
)
def test_unrecognized_section_heading_ends_bibliography(section_heading):
    text = (
        "References\nAda Author (2022). A Useful Study.\n\n"
        f"{section_heading}\nJane Doe (2022). Student medical accommodation."
    )
    found = extract_bibliography(text)
    assert len(found) == 1
    assert all("Jane" not in item.query for item in found)
    assert all("medical" not in item.query.casefold() for item in found)


def test_answer_key_content_never_reaches_search_query():
    source = (
        "References\nAda Author (2022). A Useful Study.\n\n"
        "Answer Key\n"
        "Jane Doe (2022). Student medical accommodation and private health details."
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200,
                {},
                DDG_EMPTY,
            )
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    search_requests = [
        request for request in transport.requests if request.kind == "duckduckgo"
    ]
    assert report["coverage"]["found"] == 1
    assert len(search_requests) == 2
    query = parse_qs(urlparse(search_requests[0].url).query)["q"][0]
    assert "A Useful Study" in query
    assert "Jane" not in query
    assert "medical" not in query.casefold()


def test_indented_unknown_heading_and_private_entry_never_reach_search_query():
    source = (
        "References\nAda Author (2022). A Useful Study.\n"
        "  Answer Key\n"
        "  Jane Doe (2022). Student medical accommodation and private health details."
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200,
                {},
                DDG_EMPTY,
            )
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    search_requests = [
        request for request in transport.requests if request.kind == "duckduckgo"
    ]
    assert report["coverage"]["found"] == 1
    assert len(search_requests) == 2
    query = parse_qs(urlparse(search_requests[0].url).query)["q"][0]
    assert "A Useful Study" in query
    assert "Jane" not in query
    assert "medical" not in query.casefold()


@pytest.mark.parametrize(
    ("heading", "indent"),
    [
        (heading, indent)
        for heading in (
            "Publisher Notes",
            "Retrieved Student Records",
            "Journal of Student Records",
        )
        for indent in ("", "  ")
    ],
)
def test_unrecognized_heading_without_blank_line_never_reaches_search_query(
    heading, indent
):
    source = (
        "References\nAda Author (2022). A Useful Study.\n"
        f"{indent}{heading}\n"
        f"{indent}Jane Doe (2022). Student medical accommodation and "
        "private health details."
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200,
                {},
                DDG_EMPTY,
            )
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    search_requests = [
        request for request in transport.requests if request.kind == "duckduckgo"
    ]
    assert report["coverage"]["found"] == 1
    assert len(search_requests) == 2
    query = parse_qs(urlparse(search_requests[0].url).query)["q"][0]
    assert "A Useful Study" in query
    assert "Jane" not in query
    assert "medical" not in query.casefold()


@pytest.mark.parametrize(
    "section_heading",
    ["Appendix A: Student Records", "2. Assessment: Student Details"],
)
def test_titled_section_heading_stops_private_records(section_heading):
    text = (
        "References\n[1] Ada Author (2022). A Useful Study.\n"
        f"{section_heading}\n"
        "Jane Doe (2022). Student medical accommodation and private health details."
    )
    found = extract_bibliography(text)
    assert len(found) == 1
    assert all("Jane" not in item.query for item in found)
    assert all("medical" not in item.query.casefold() for item in found)


def test_adjacent_apa_entries_keep_years_and_doi_with_the_correct_reference():
    text = (
        "References\n"
        "Smith, A. (2020). First Study.\n"
        "Journal of Useful Research, 15(2), 10-20.\n"
        "Jones, B. (2021). Second Study.\n"
        "Journal of Relevant Research. https://doi.org/10.1234/second\n"
    )
    found = extract_bibliography(text)
    assert len(found) == 2
    assert found[0].reference.title == "First Study"
    assert found[0].reference.year == 2020
    assert found[0].reference.doi is None
    assert found[1].reference.title == "Second Study"
    assert found[1].reference.year == 2021
    assert found[1].reference.doi == "10.1234/second"


def test_title_only_and_header_only_source_cannot_claim_match():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    html = (
        b"<html><head><title>Unrelated Publisher Home</title></head><body>"
        b"<nav>A Useful Study</nav><header>A useful study</header><p>"
        b"This useful study appears in a general publisher landing page with "
        b"substantial unrelated information and navigation surrounding it.</p>"
        b"</body></html>"
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(200, {}, ddg_result()),
            "https://example.org/study": Response(
                200, {"content-type": "text/html"}, html
            ),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    assert report["references"][0]["status"] == "unverified"
    assert report["references"][0]["title"] == "Unrelated Publisher Home"
    assert "This useful study" in report["references"][0]["excerpt"]
    assert report["references"][0]["source_attempts"][0]["reason"] == "title_mismatch"


def test_title_only_source_has_no_body_excerpt_and_cannot_match():
    source = "References\n[1] Ada Author (2022). A Useful Study."
    html = (
        b"<html><head><title>A Useful Study</title></head><body>"
        b"<nav>A Useful Study</nav><header>A Useful Study</header></body></html>"
    )
    transport = FakeTransport(
        {
            "duckduckgo": Response(200, {}, ddg_result()),
            "https://example.org/study": Response(200, {}, html),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    assert report["references"][0]["status"] == "unverified"
    assert report["references"][0]["excerpt"] is None
    assert (
        report["references"][0]["source_attempts"][0]["reason"]
        == "no_substantive_passage"
    )


def test_enabled_call_fails_when_global_config_changes_after_admission():
    class DisabledSettings:
        enabled = False

    with pytest.raises(ReferenceToolsUnavailable) as exc:
        asyncio.run(
            build_public_reference_report(
                "References\n[1] Ada Author (2022). A Useful Study.",
                enabled=True,
                settings=DisabledSettings(),
                transport=FakeTransport({}),
            )
        )
    assert exc.value.code == Code.DISABLED


def test_search_readiness_does_not_require_provider_key():
    class NoSearch:
        enabled = True

    transport = FakeTransport(
        {
            "duckduckgo": Response(
                200,
                {},
                DDG_EMPTY,
            )
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=NoSearch(),
            transport=transport,
        )
    )
    assert report["provider"] == "duckduckgo_html"
    assert report["attempts"] == {"search": 2, "source": 0}
    assert readiness_config(NoSearch(), enabled=True, needs_search=True)["ready"]


def test_search_provider_failure_is_recorded_and_source_less_pipeline_still_fails():
    class FailingProvider:
        async def get(self, request, deadline):
            if request.kind == "duckduckgo":
                return Response(503, {}, b"")
            return Response(404, {}, b"")

    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=FailingProvider(),
        )
    )
    assert set(report["references"][0]["errors"]) == {Code.HTTP.value}
    assert report["attempts"]["search"] == 4
    with pytest.raises(AgentExecutionError, match="usable public reference passage"):
        _references(
            SimpleNamespace(
                precomputed_context={
                    "public_reference_verification": (json.dumps(report),)
                },
                form_snapshot=SimpleNamespace(adapter_version=3),
            )
        )


def test_transient_search_503_retries_once_and_keeps_usable_passage():
    class RecoveringProvider:
        requests = []

        async def get(self, request, deadline):
            self.requests.append(request)
            if request.kind == "duckduckgo":
                if sum(item.kind == "duckduckgo" for item in self.requests) == 1:
                    return Response(503, {}, b"")
                return Response(200, {}, ddg_result())
            return Response(
                200,
                {},
                b"<html><head><title>A Useful Study</title></head><body><p>"
                b"This useful study reports detailed findings and methods from a"
                b" reproducible analysis at multiple sites.</p></body></html>",
            )

    transport = RecoveringProvider()
    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=transport,
        )
    )
    assert report["references"][0]["status"] == "matched"
    assert report["attempts"] == {"search": 2, "source": 1}


def test_global_deadline_keeps_completed_reference_and_stops_requests():
    class Clock:
        value = 0

        def __call__(self):
            return self.value

    clock = Clock()
    page = (
        b"<html><head><title>A Useful Study</title></head><body><p>"
        b"This useful study reports detailed findings and methods from a"
        b" reproducible analysis at multiple sites.</p></body></html>"
    )

    class DeadlineTransport:
        requests = []

        async def get(self, request, deadline):
            self.requests.append(request)
            if request.kind == "duckduckgo":
                return Response(200, {}, ddg_result())
            clock.value = 45
            return Response(200, {}, page)

    transport = DeadlineTransport()
    report = asyncio.run(
        build_public_reference_report(
            "References\n"
            "[1] Ada Author (2022). A Useful Study.\n"
            "[2] Bea Author (2023). Another Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=transport,
            clock=clock,
        )
    )
    assert len(report["references"]) == 1
    assert report["references"][0]["status"] == "matched"
    assert report["coverage"] == {"found": 2, "checked": 1, "skipped": 1, "total": 2}
    assert len(transport.requests) == 2


def test_registry_provider_failure_falls_back_without_claiming_registry_match():
    class FailingRegistry:
        async def get(self, request, deadline):
            if request.kind == "crossref":
                return Response(503, {}, b"")
            return Response(404, {}, b"")

    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study. "
            "https://doi.org/10.1234/original",
            enabled=True,
            settings=Settings(),
            transport=FailingRegistry(),
        )
    )
    row = report["references"][0]
    assert row["registry_status"] == "unavailable"
    assert row["registry_matched_fields"] == []
    assert set(row["errors"]) == {Code.HTTP.value}
    assert report["attempts"]["search"] >= 1


def test_registry_failure_plus_matching_page_is_usable_but_metadata_ambiguous():
    class RegistryFailureWithPage:
        async def get(self, request, deadline):
            if request.kind == "crossref":
                return Response(503, {}, b"")
            if request.kind == "datacite":
                return Response(404, {}, b"")
            if request.kind == "duckduckgo":
                return Response(200, {}, ddg_result())
            return Response(
                200,
                {},
                b"<html><head><title>A Useful Study</title></head><body><p>"
                b"This useful study reports detailed findings and methods from a"
                b" reproducible analysis at multiple sites.</p></body></html>",
            )

    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study. "
            "https://doi.org/10.1234/original",
            enabled=True,
            settings=Settings(),
            transport=RegistryFailureWithPage(),
        )
    )
    row = report["references"][0]
    assert row["registry_status"] == "unavailable"
    assert row["status"] == "ambiguous"
    assert row["matched_fields"] == ["page_title"]
    assert set(row["unverified_fields"]) == {"author", "year", "doi"}
    assert row["registry_matched_fields"] == []
    assert _references(
        SimpleNamespace(
            precomputed_context={
                "public_reference_verification": (json.dumps(report),)
            },
            form_snapshot=SimpleNamespace(adapter_version=3),
        )
    ) == [json.dumps(report)]


def test_provider_timeout_is_recorded_and_safe_to_continue():
    class SlowProvider:
        async def get(self, request, deadline):
            raise TimeoutError

    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=SlowProvider(),
        )
    )
    assert report["references"][0]["errors"] == [
        Code.DEADLINE.value,
        Code.DEADLINE.value,
    ]


@pytest.mark.parametrize(
    (
        "registry_doi",
        "registry_year",
        "expected_status",
        "expected_registry_status",
        "expected_mismatch",
    ),
    [
        ("10.1234/different", 2022, "mismatched", "mismatched", ["doi"]),
        ("10.1234/original", 2020, "ambiguous", "ambiguous", []),
    ],
)
def test_page_title_never_overrides_registry_conflict(
    registry_doi,
    registry_year,
    expected_status,
    expected_registry_status,
    expected_mismatch,
):
    from urllib.parse import quote

    source = (
        "References\n[1] Ada Author (2022). A Useful Study. "
        "https://doi.org/10.1234/original"
    )
    crossref_url = "https://api.crossref.org/works/" + quote(
        "10.1234/original", safe=""
    )
    registry = {
        "status": "ok",
        "message-type": "work",
        "message": {
            "title": ["A Useful Study"],
            "DOI": registry_doi,
            "author": [{"given": "Ada", "family": "Author"}],
            "published": {"date-parts": [[registry_year]]},
        },
    }
    page = (
        b"<html><head><title>A Useful Study</title></head><body><p>"
        b"This useful study presents the detailed research methods and findings "
        b"from a multi-year investigation conducted across several sites.</p>"
        b"</body></html>"
    )
    transport = FakeTransport(
        {
            crossref_url: Response(200, {}, json.dumps(registry).encode()),
            "duckduckgo": Response(200, {}, ddg_result()),
            "https://example.org/study": Response(200, {}, page),
        }
    )
    report = asyncio.run(
        build_public_reference_report(
            source, enabled=True, settings=Settings(), transport=transport
        )
    )
    result = report["references"][0]
    assert result["status"] == expected_status
    assert result["registry_status"] == expected_registry_status
    assert result["registry_mismatches"] == expected_mismatch
    assert "page_title" not in result["matched_fields"]
    if expected_registry_status == "mismatched":
        encoded = json.dumps(report)
        assert _references(
            SimpleNamespace(
                precomputed_context={"public_reference_verification": (encoded,)},
                form_snapshot=SimpleNamespace(adapter_version=3),
            )
        ) == [encoded]


def test_readiness_requires_search_provider_only_when_search_is_needed():
    class NoSearch:
        enabled = True

    assert readiness_config(NoSearch(), enabled=True, needs_search=False)["ready"]
    assert (
        readiness_config(NoSearch(), enabled=True, needs_search=True)["reason"] is None
    )


RECOVERED_PAGE = (
    b"<html><head><title>A Useful Study</title></head><body><p>"
    b"A useful study reports detailed findings and methods from a "
    b"reproducible analysis at multiple sites.</p></body></html>"
)


class QueryAwareTransport(FakeTransport):
    def __init__(self, search_responses, page_responses):
        super().__init__({})
        self.search_responses = search_responses
        self.responses = page_responses

    async def get(self, request, deadline):
        self.requests.append(request)
        if request.kind == "duckduckgo":
            query = parse_qs(urlparse(request.url).query)["q"][0]
            return self.search_responses[query]
        response = self.responses.get(request.url, Response(404, {}, b""))
        if isinstance(response, Exception):
            raise response
        return response


def _reference_query(title, *metadata):
    return " ".join((title, *metadata))


def test_title_only_fallback_recovers_page_and_report_passes_harness_gate():
    title = "A Useful Study"
    primary = _reference_query(title, "Ada Author", "2022")
    transport = QueryAwareTransport(
        {
            primary: Response(200, {}, DDG_EMPTY),
            title: Response(
                200, {}, ddg_result("A Useful Study", "https://example.org/recovered")
            ),
        },
        {"https://example.org/recovered": Response(200, {}, RECOVERED_PAGE)},
    )
    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=transport,
        )
    )
    row = report["references"][0]
    assert row["status"] == "matched"
    assert [attempt["query_scope"] for attempt in row["search_attempts"]] == [
        "primary",
        "title_only",
    ]
    assert [attempt["candidate_count"] for attempt in row["search_attempts"]] == [0, 1]
    assert row["excerpt"]
    assert _references(
        SimpleNamespace(
            precomputed_context={
                "public_reference_verification": (json.dumps(report),)
            },
            form_snapshot=SimpleNamespace(adapter_version=3),
        )
    ) == [json.dumps(report)]


def test_title_only_fallback_runs_after_primary_candidates_are_blocked():
    title = "A Useful Study"
    primary = _reference_query(title, "Ada Author", "2022")
    transport = QueryAwareTransport(
        {
            primary: Response(
                200, {}, ddg_result("A Useful Study", "https://example.org/blocked")
            ),
            title: Response(
                200, {}, ddg_result("A Useful Study", "https://example.org/recovered")
            ),
        },
        {
            "https://example.org/blocked": Response(403, {}, b""),
            "https://example.org/recovered": Response(200, {}, RECOVERED_PAGE),
        },
    )
    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=transport,
        )
    )
    row = report["references"][0]
    assert row["status"] == "matched"
    assert row["source_url"] == "https://example.org/recovered"
    assert report["attempts"] == {"search": 2, "source": 2}


def test_usable_primary_page_skips_title_only_fallback():
    title = "A Useful Study"
    primary = _reference_query(title, "Ada Author", "2022")
    transport = QueryAwareTransport(
        {
            primary: Response(
                200, {}, ddg_result("A Useful Study", "https://example.org/primary")
            ),
            title: Response(200, {}, DDG_EMPTY),
        },
        {"https://example.org/primary": Response(200, {}, RECOVERED_PAGE)},
    )
    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=transport,
        )
    )
    assert report["attempts"]["search"] == 1
    assert [
        item["query_scope"] for item in report["references"][0]["search_attempts"]
    ] == ["primary"]


def test_failed_title_only_fallback_never_verifies_without_a_page():
    title = "A Useful Study"
    primary = _reference_query(title, "Ada Author", "2022")
    transport = QueryAwareTransport(
        {
            primary: Response(200, {}, DDG_EMPTY),
            title: Response(
                200, {}, ddg_result("A Useful Study", "https://example.org/blocked")
            ),
        },
        {"https://example.org/blocked": Response(403, {}, b"")},
    )
    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=transport,
        )
    )
    row = report["references"][0]
    assert report["attempts"]["search"] == 2
    assert row["status"] == "unavailable"
    assert row["source_url"] is None
    assert row["excerpt"] is None
    with pytest.raises(AgentExecutionError, match="usable public reference passage"):
        _references(
            SimpleNamespace(
                precomputed_context={
                    "public_reference_verification": (json.dumps(report),)
                },
                form_snapshot=SimpleNamespace(adapter_version=3),
            )
        )


def test_topic_query_is_already_title_only_and_is_not_repeated():
    transport = FakeTransport({"duckduckgo": Response(200, {}, DDG_EMPTY)})
    report = asyncio.run(
        build_public_reference_report(
            "Lesson Title: A Useful Study",
            enabled=True,
            settings=Settings(),
            transport=transport,
        )
    )
    assert report["attempts"]["search"] == 1
    assert report["references"][0]["search_attempts"] == [
        {"query_scope": "primary", "candidate_count": 0, "outcome": "no_candidates"}
    ]


def test_fallback_skips_previously_blocked_candidate_urls():
    title = "A Useful Study"
    blocked = "https://example.org/blocked"
    recovered = "https://example.org/recovered"
    transport = QueryAwareTransport(
        {
            _reference_query(title, "Ada Author", "2022"): Response(
                200, {}, ddg_result(title, blocked)
            ),
            title: Response(200, {}, ddg_results((title, blocked), (title, recovered))),
        },
        {blocked: Response(403, {}, b""), recovered: Response(200, {}, RECOVERED_PAGE)},
    )
    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=transport,
        )
    )
    assert [
        request.url for request in transport.requests if request.kind == "document"
    ] == [blocked, recovered]
    assert report["references"][0]["source_url"] == recovered


def test_fallback_shares_original_total_deadline():
    class Clock:
        value = 0

        def __call__(self):
            return self.value

    clock = Clock()

    class TimedTransport:
        deadlines = []
        searches = 0

        async def get(self, request, deadline):
            self.deadlines.append(deadline)
            if deadline - clock.value < 4:
                clock.value = deadline
                raise TimeoutError
            clock.value += 4
            if request.kind == "duckduckgo":
                self.searches += 1
                return Response(
                    200,
                    {},
                    ddg_results(
                        *[
                            (
                                "A Useful Study",
                                f"https://example.org/{self.searches}-{index}",
                            )
                            for index in range(5)
                        ]
                    ),
                )
            return Response(403, {}, b"")

    transport = TimedTransport()
    report = asyncio.run(
        build_public_reference_report(
            "References\n[1] Ada Author (2022). A Useful Study.",
            enabled=True,
            settings=Settings(),
            transport=transport,
            clock=clock,
        )
    )
    assert report["references"][0]["status"] == "unavailable"
    assert transport.searches == 2
    assert max(transport.deadlines) == clock.value == 45
