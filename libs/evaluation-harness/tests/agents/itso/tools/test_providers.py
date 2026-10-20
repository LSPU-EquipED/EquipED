from urllib.parse import parse_qs, quote, urlsplit

import pytest
from equiped_harness.agents.itso.tools.contracts import (
    Code,
    PublicReference,
    VerificationError,
)
from equiped_harness.agents.itso.tools.providers import (
    duckduckgo_url,
    parse_duckduckgo,
)


def reference():
    return PublicReference(
        source_id="ref-1",
        visibility="user_approved_public",
        origin="approved_reference_inventory",
        tags=("title", "author", "year"),
        title="Sustainable Agriculture in Small Island Communities",
        authors=("Ada Example",),
        year=2022,
    )


def result(href, title):
    return f'<a class="result__a" href="{href}">{title}</a>'


def test_duckduckgo_url_uses_only_approved_fields():
    query = parse_qs(urlsplit(duckduckgo_url(reference())).query)
    assert query == {
        "q": ["Sustainable Agriculture in Small Island Communities Ada Example 2022"]
    }
    assert "kl" not in query


def test_actual_result_anchor_syntax_unwraps_destination_and_keeps_title_suffix():
    destination = "https://example.org/articles/42?doi=10.1234%2Fsample"
    wrapped = (
        "https://duckduckgo.com/l/?uddg="
        + quote(destination, safe="")
        + "&rut=tracking"
    )
    title = "Sustainable Agriculture in Small Island Communities - Example Journal"
    html = f'<html><div class="results">{result(wrapped, title)}</div></html>'
    candidates = parse_duckduckgo(html.encode(), reference())
    assert len(candidates) == 1
    assert candidates[0].url == destination
    assert candidates[0].title.endswith("Example Journal")
    assert candidates[0].match_code == "title_relevant"


def test_direct_https_results_are_accepted_when_title_is_relevant():
    html = result(
        "https://example.org/articles/42?doi=10.1234%2Fsample",
        "Sustainable Agriculture in Island Communities | Example Journal",
    )
    candidates = parse_duckduckgo(html.encode(), reference())
    assert len(candidates) == 1
    assert candidates[0].url == "https://example.org/articles/42?doi=10.1234%2Fsample"
    assert candidates[0].match_code == "title_relevant"


def test_candidate_limit_is_bounded_and_defaults_to_legacy_three():
    html = "".join(
        result(
            f"https://example.org/{index}",
            "Sustainable Agriculture Small Island Communities",
        )
        for index in range(1, 7)
    )
    body = html.encode()
    assert len(parse_duckduckgo(body, reference())) == 3
    assert len(parse_duckduckgo(body, reference(), candidate_limit=5)) == 5
    with pytest.raises(ValueError):
        parse_duckduckgo(body, reference(), candidate_limit=6)


def test_explicit_empty_and_challenge_pages_are_distinguished():
    assert (
        parse_duckduckgo(b'<div class="no-results">No results</div>', reference()) == ()
    )
    with pytest.raises(VerificationError) as exc:
        parse_duckduckgo(b'<form id="challenge-form">captcha</form>', reference())
    assert exc.value.code == Code.ACCESS
    with pytest.raises(VerificationError) as exc:
        parse_duckduckgo(
            b"<html><body>temporarily unavailable</body></html>", reference()
        )
    assert exc.value.code == Code.MALFORMED


@pytest.mark.parametrize(
    "href",
    [
        "https://evil.example/l/?uddg=https%3A%2F%2Fexample.org%2F",
        "https://duckduckgo.com/redirect?uddg=https%3A%2F%2Fexample.org%2F",
        "https://duckduckgo.com/l/?uddg=https%3A%2F%2F127.0.0.1%2F",
        "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Ffile.pdf",
        "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2F%3Ftoken%3Dsecret",
    ],
)
def test_unknown_or_unsafe_destinations_are_never_candidates(href):
    html = result(href, "Sustainable Agriculture in Small Island Communities")
    assert parse_duckduckgo(html.encode(), reference()) == ()
