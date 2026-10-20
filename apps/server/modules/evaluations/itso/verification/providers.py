"""Strict allowlisted metadata parsing, never claim verification or abstracts."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from .contracts import (
    Candidate,
    Code,
    Metadata,
    PublicReference,
    VerificationError,
    clean_field,
)
from .transport import validate_url


def strict_json(body: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def constant(_):
        raise ValueError

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError
        return number

    try:
        obj = json.loads(
            body,
            object_pairs_hook=pairs,
            parse_constant=constant,
            parse_float=finite_float,
        )
        if not isinstance(obj, dict):
            raise ValueError
        return obj
    except (ValueError, UnicodeError, RecursionError):
        raise VerificationError(Code.MALFORMED) from None


def text(value, maximum=300) -> str:
    if not isinstance(value, str) or not clean_field(value, maximum):
        raise VerificationError(Code.MALFORMED)
    return value


def array(value, maximum=100):
    if not isinstance(value, list) or len(value) > maximum:
        raise VerificationError(Code.MALFORMED)
    return value


def record(value) -> dict:
    if not isinstance(value, dict):
        raise VerificationError(Code.MALFORMED)
    return value


def deposited_doi(value) -> str:
    doi = text(value, 200)
    if not re.fullmatch(r"10\.\d{4,9}/[A-Za-z0-9._;()/:+-]{1,180}", doi):
        raise VerificationError(Code.MALFORMED)
    return doi


def optional_url(value) -> str | None:
    if value is None:
        return None
    url = text(value, 2048)
    try:
        validate_url(url)
    except VerificationError:
        # Deposited DOI resolver/full-text/unsafe links are not page candidates.
        return None
    if url.startswith("https://doi.org/"):
        return None
    return url


def normalize(value: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", value).casefold()))


def parse_crossref(body: bytes) -> Metadata:
    obj = strict_json(body)
    message = record(obj.get("message"))
    if obj.get("status") != "ok" or obj.get("message-type") != "work":
        raise VerificationError(Code.MALFORMED)
    titles = array(message.get("title"), 10)
    if not titles:
        raise VerificationError(Code.MALFORMED)
    title = text(titles[0])
    doi = deposited_doi(message.get("DOI"))
    authors = []
    for item in array(message.get("author", []), 100):
        item = record(item)
        family = item.get("family")
        name = (
            " ".join(
                filter(
                    None,
                    [
                        text(item["given"], 100) if "given" in item else None,
                        text(family, 100),
                    ],
                )
            )
            if family
            else item.get("name")
        )
        authors.append(text(name, 200))
    years = []
    for key in ("published", "published-print", "published-online", "issued"):
        if key not in message:
            continue
        dates = array(record(message[key]).get("date-parts"), 4)
        for date in dates:
            date = array(date, 3)
            if not date or type(date[0]) is not int or not 1400 <= date[0] <= 2200:
                raise VerificationError(Code.MALFORMED)
            years.append(date[0])
    publisher = text(message["publisher"], 200) if "publisher" in message else None
    # Do not follow DOI resolver URLs or Crossref link/full-text fields.
    return Metadata(
        doi=doi,
        title=title,
        authors=tuple(authors),
        years=tuple(sorted(set(years))),
        publisher=publisher,
        url=optional_url(message.get("URL")),
    )


def parse_datacite(body: bytes) -> Metadata:
    data = record(strict_json(body).get("data"))
    if data.get("type") != "dois":
        raise VerificationError(Code.MALFORMED)
    attrs = record(data.get("attributes"))
    doi = deposited_doi(attrs.get("doi"))
    if text(data.get("id"), 200).casefold() != doi.casefold():
        raise VerificationError(Code.MALFORMED)
    titles = array(attrs.get("titles"), 20)
    if not titles:
        raise VerificationError(Code.MALFORMED)
    authors = []
    for creator in array(attrs.get("creators", []), 100):
        creator = record(creator)
        if creator.get("familyName"):
            author = " ".join(
                filter(
                    None,
                    [
                        text(creator["givenName"], 100)
                        if creator.get("givenName")
                        else None,
                        text(creator["familyName"], 100),
                    ],
                )
            )
        else:
            author = text(creator.get("name"), 200)
        authors.append(text(author, 200))
    year = attrs.get("publicationYear")
    if type(year) is not int or not 1400 <= year <= 2200:
        raise VerificationError(Code.MALFORMED)
    return Metadata(
        doi=doi,
        title=text(record(titles[0]).get("title")),
        authors=tuple(authors),
        years=(year,),
        publisher=text(attrs["publisher"], 200) if "publisher" in attrs else None,
        url=optional_url(attrs.get("url")),
    )


def match_metadata(ref: PublicReference, meta: Metadata):
    matched, mismatched, uncertain = [], [], False
    if ref.doi:
        if meta.doi and ref.doi.casefold() == meta.doi.casefold():
            matched.append("doi")
        elif meta.doi:
            mismatched.append("doi")
        else:
            uncertain = True
    if ref.title:
        if meta.title and normalize(ref.title) == normalize(meta.title):
            matched.append("title")
        elif meta.title:
            # Subtitle, transliteration and edition variants need review, not
            # an automatic false identity conflict.
            uncertain = True
        else:
            uncertain = True
    if ref.authors:
        expected = {normalize(a) for a in ref.authors}
        actual = {normalize(a) for a in meta.authors}
        if expected and expected <= actual:
            matched.append("author")
        else:
            uncertain = True  # initials/order/consortium variants
    if ref.year:
        if ref.year in meta.years:
            matched.append("year")
        else:
            uncertain = True  # deposited online/print/edition dates vary
    status = (
        "mismatched"
        if mismatched
        else ("ambiguous" if uncertain else "matched" if matched else "found")
    )
    return status, tuple(matched), tuple(mismatched)


def brave_url(ref: PublicReference) -> str:
    # Exact approved fields only, no arbitrary model query or description.
    fields = [ref.title or "", *ref.authors]
    if ref.doi:
        fields.append(ref.doi)
    if ref.year:
        fields.append(str(ref.year))
    query = " ".join(fields)
    if len(query) > 1200:
        raise VerificationError(Code.INVALID, ref.reference_hash)
    return "https://api.search.brave.com/res/v1/web/search?" + urlencode(
        {"q": query, "count": 3, "safesearch": "strict", "text_decorations": "false"}
    )


def duckduckgo_url(ref: PublicReference) -> str:
    """Build a search URL only from the approved public bibliography fields."""
    fields = [ref.title or "", *ref.authors]
    if ref.doi:
        fields.append(ref.doi)
    if ref.year:
        fields.append(str(ref.year))
    query = " ".join(fields)
    if not query or len(query) > 1200:
        raise VerificationError(Code.INVALID, ref.reference_hash)
    return "https://html.duckduckgo.com/html/?" + urlencode({"q": query})


def doi_url(provider: str, doi: str) -> str:
    return {
        "crossref": "https://api.crossref.org/works/",
        "datacite": "https://api.datacite.org/dois/",
    }[provider] + quote(doi, safe="")


def parse_brave(body: bytes, ref: PublicReference) -> tuple[Candidate, ...]:
    obj = strict_json(body)
    if "web" not in obj:
        # Brave may omit result sections for a genuine empty search, but an
        # arbitrary/error object is not a valid empty result.
        if obj.get("type") == "search" and isinstance(obj.get("query"), dict):
            text(obj["query"].get("original"), 1200)
            return ()
        raise VerificationError(Code.MALFORMED)
    web = record(obj["web"])
    results = array(web.get("results"), 50)
    candidates = []
    seen = set()
    for result in results:
        result = record(result)
        title = text(result.get("title"))
        url = text(result.get("url"), 2048)
        # Validate descriptions, but never capture paragraphs or use them as
        # source evidence. They cannot authorize new query fields.
        if "description" in result:
            text(result["description"], 2000)
        safe = optional_url(url)
        if not safe or safe in seen:
            continue
        match_code = None
        if ref.title and normalize(ref.title) == normalize(title):
            match_code = "title_exact"
        if match_code:
            candidates.append(Candidate(url=safe, title=title, match_code=match_code))
            seen.add(safe)
        if len(candidates) == 3:
            break
    return tuple(candidates)


def _title_words(value: str) -> set[str]:
    # Ignore short/common words and likely site-name suffixes. Require enough
    # distinctive overlap to avoid presenting unrelated search results.
    ignored = {"the", "and", "for", "with", "from", "into", "using", "study", "based"}
    return {w for w in normalize(value).split() if len(w) > 2 and w not in ignored}


class _DuckDuckGoParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[tuple[str, str]] = []
        self._active = False
        self._href = ""
        self._text: list[str] = []
        self.no_results = False
        self.challenge = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        marker = (attrs.get("id") or "").casefold()
        if tag == "a" and "result__a" in classes:
            self._active, self._href, self._text = True, attrs.get("href") or "", []
        if "no-results" in classes or marker == "no-results":
            self.no_results = True
        if marker in {"challenge-form", "captcha", "challenge"} or "captcha" in classes:
            self.challenge = True

    def handle_endtag(self, tag):
        if tag == "a" and self._active:
            self.results.append((self._href, " ".join("".join(self._text).split())))
            self._active = False

    def handle_data(self, data):
        if self._active:
            self._text.append(data)


def _ddg_destination(href: str) -> str | None:
    """Unwrap the recognized DDG wrapper, or accept a validated direct link."""
    try:
        parsed = urlsplit(href)
        host = parsed.hostname
        is_ddg = host in {"duckduckgo.com", "html.duckduckgo.com"}
        values = parse_qs(parsed.query, keep_blank_values=True).get("uddg", [])
        if parsed.path == "/l/" and is_ddg:
            if parsed.scheme not in {"", "https"} or len(values) != 1 or not values[0]:
                return None
            validate_url(values[0])
            return values[0]
        # Do not reinterpret an unrecognized host's redirect as a direct link.
        if parsed.path == "/l/" and values:
            return None
        if is_ddg or parsed.scheme != "https" or not host:
            return None
        validate_url(href)
        return href
    except (ValueError, VerificationError):
        return None


def parse_duckduckgo(
    body: bytes, ref: PublicReference, *, candidate_limit: int = 3
) -> tuple[Candidate, ...]:
    if type(candidate_limit) is not int or not 1 <= candidate_limit <= 5:
        raise ValueError("candidate_limit must be between 1 and 5")
    try:
        html = body.decode("utf-8", errors="strict")
        if len(html) > 128 * 1024:
            raise ValueError
        parser = _DuckDuckGoParser()
        parser.feed(html)
        parser.close()
    except (UnicodeError, ValueError, RecursionError):
        raise VerificationError(Code.MALFORMED) from None
    if parser.challenge or re.search(
        r"(?i)captcha|bot challenge|anomaly detected", html
    ):
        raise VerificationError(Code.ACCESS)
    if not parser.results:
        if parser.no_results or re.search(r"(?is)no results found", html):
            return ()
        raise VerificationError(Code.MALFORMED)

    expected = _title_words(ref.title or "")
    if not expected:
        return ()
    candidates, seen = [], set()
    for href, title in parser.results:
        if not title or len(title) > 300:
            continue
        words = _title_words(title)
        # A couple of discriminating title terms are required; a website suffix
        # cannot suppress an otherwise relevant hit.
        overlap = len(expected & words)
        if overlap < min(2, len(expected)):
            continue
        if expected and overlap / len(expected) < 0.45:
            continue
        destination = _ddg_destination(href)
        if not destination or destination in seen:
            continue
        candidates.append(
            Candidate(url=destination, title=title, match_code="title_relevant")
        )
        seen.add(destination)
        if len(candidates) == candidate_limit:
            break
    return tuple(candidates)
