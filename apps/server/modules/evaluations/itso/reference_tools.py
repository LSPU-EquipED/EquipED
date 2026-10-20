"""Bounded public reference and labelled-topic search for ITSO.

Only entries found under an explicit bibliography/references heading are sent to
external providers. SLM prose outside that section is never used as a query.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

from .verification.contracts import Code, PublicReference, VerificationError
from .verification.providers import (
    doi_url,
    duckduckgo_url,
    match_metadata,
    parse_crossref,
    parse_datacite,
    parse_duckduckgo,
)
from .verification.transport import (
    DOCUMENT_LIMIT,
    LIMIT,
    PinnedHTTPS,
    Request,
    Transport,
    validate_url,
)

REFERENCE_LIMIT = 5
BIBLIOGRAPHY_LINE_LIMIT = 500
BIBLIOGRAPHY_CHARACTER_LIMIT = 24000
TOTAL_DEADLINE_SECONDS = 45
CALL_DEADLINE_SECONDS = 5
SOURCE_CANDIDATE_LIMIT = 5
SOURCE_REDIRECT_LIMIT = 2
SCOPE = ("ITSO-01", "ITSO-02")


@dataclass(frozen=True)
class BibliographyItem:
    reference: PublicReference
    query: str
    query_kind: str = "bibliography"
    citation_section: str = "references"


class _PageParser(HTMLParser):
    """Extract a page title and bounded visible body text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self.skip_tags: list[str] = []
        self.block: list[str] = []
        self.body_characters = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {name.casefold(): value or "" for name, value in attrs}
        classes = attributes.get("class", "").casefold()
        identity = attributes.get("id", "").casefold()
        label = attributes.get("aria-label", "").casefold()
        navigation = attributes.get("role", "").casefold() == "navigation"
        breadcrumb = (
            "breadcrumb" in classes or "breadcrumb" in identity or "breadcrumb" in label
        )
        if (
            tag
            in {
                "script",
                "style",
                "noscript",
                "svg",
                "nav",
                "header",
                "footer",
                "aside",
                "title",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
            }
            or navigation
            or breadcrumb
        ):
            self.skip_tags.append(tag)
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip_tags:
            self.skip_tags.remove(tag)
        if tag == "title":
            self.in_title = False
        if tag in {
            "p",
            "li",
            "blockquote",
            "h1",
            "h2",
            "h3",
            "h4",
            "article",
            "section",
        }:
            self._flush_block()

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if not clean:
            return
        if self.in_title:
            self.title_parts.append(clean)
        if self.skip_tags:
            return
        if self.body_characters < 24000:
            self.block.append(clean)
            self.body_characters += len(clean)

    def _flush_block(self) -> None:
        value = " ".join(self.block).strip()
        if value:
            self.body_parts.append(value)
        self.block.clear()


def extract_bibliography(text: str) -> tuple[BibliographyItem, ...]:
    """Read citations from a bounded bibliography section and stop at its boundary.

    A bibliography has no universally reliable heading vocabulary. Treat only
    recognizable citations and their formatting continuations as section
    contents; any other line is an ambiguous boundary and ends parsing.
    """
    lines = text.splitlines()[:12000]
    start = None
    section_name = "references"
    heading = re.compile(
        r"^\s*(?:references|bibliography|works cited|selected references)\s*:?\s*$",
        re.I,
    )
    learning_heading = re.compile(
        r"\blearning\s+resources\b(?=\s*:?(?:\s*\d{1,3}[.)]\s+|\s*$))",
        re.I | re.M,
    )
    for i, line in enumerate(lines):
        if heading.match(line.strip(" #*\t")):
            start = i + 1
            break
        learning_match = learning_heading.search(line)
        if learning_match:
            start = i
            section_name = "learning_resources"
            lines[i] = line[learning_match.end() :].lstrip(" :\t")
            break
    if start is None:
        return ()
    entries: list[str] = []
    current = ""
    section_characters = 0
    citation_year = re.compile(
        r"^(.{3,180}?)\s+\(?(?:1[4-9]\d{2}|20\d{2}|21\d{2}|2200)\)?[.,]?\s+"
    )
    continuation_start = re.compile(
        r"^(?:journal\s+of\b.*(?:\d+\s*\(\d+\)\s*,?\s*"
        r"(?:pp?\.?\s*)?\d+(?:[-–]\d+)?|"
        r"https?://doi\.org/10\.\d{4,9}/[A-Za-z0-9._;()/:+-]+)|"
        r"(?:vol(?:ume)?\.?\s*)?\d+\s*\(\d+\)(?:[,;:]?\s*"
        r"(?:pp?\.?\s*)?\d+(?:[-–]\d+)?)?|"
        r"(?:https?://doi\.org/|doi:\s*)10\.\d{4,9}/"
        r"[A-Za-z0-9._;()/:+-]+)\s*[.,]?$",
        re.I,
    )
    if section_name == "learning_resources":
        # OCR commonly flattens the heading and numbered list onto one line.
        # Split only explicit list markers; all later content still passes the
        # citation parser below and an unclassified line closes the section.
        learning_lines = lines[start : start + BIBLIOGRAPHY_LINE_LIMIT]
        hard_boundary = re.compile(
            r"(?i)\b(?:prepared\s+by|assessment|discussion|learning\s+"
            r"outcomes?|objectives?|student\s+(?:details?|records?)|"
            r"learner\s+details?)\b"
        )
        for line in learning_lines:
            section_characters += len(line)
            if section_characters > BIBLIOGRAPHY_CHARACTER_LIMIT:
                break
            value = line.strip()
            if not value:
                continue
            boundary_match = hard_boundary.search(value)
            boundary_found = boundary_match is not None
            if boundary_match:
                value = value[: boundary_match.start()].rstrip()
            markers = list(re.finditer(r"(?<!\S)\d{1,3}[.)]\s+", value))
            # Never discard an unclassified prefix: it may be private text
            # before a numbered, citation-shaped body entry.
            if not markers or markers[0].start() != 0:
                break
            chunks = [
                value[
                    marker.end() : markers[idx + 1].start()
                    if idx + 1 < len(markers)
                    else len(value)
                ]
                for idx, marker in enumerate(markers)
            ]
            for chunk in chunks:
                entry = chunk.strip()
                if not entry:
                    continue
                entries.append(entry[:1200])
            if boundary_found:
                break
    else:
        for line in lines[start : start + BIBLIOGRAPHY_LINE_LIMIT]:
            section_characters += len(line)
            if section_characters > BIBLIOGRAPHY_CHARACTER_LIMIT:
                break
            value = line.strip()
            if not value:
                if current:
                    entries.append(current)
                    current = ""
                continue
            numbered = re.match(r"^(?:\[\d{1,3}\]|\d{1,3}[.)]|[-*])\s+", value)
            citation_value = value[numbered.end() :] if numbered else value
            citation_start = citation_year.match(citation_value)
            valid_citation_start = bool(
                citation_start
                and re.search(r"[A-Za-z][A-Za-z'-]{2,}", citation_start.group(1))
            )
            if valid_citation_start:
                if current:
                    entries.append(current)
                current = citation_value[:1200]
                continue

            # Wrapped APA entries commonly put journal, volume, DOI, or retrieval
            # details on the next line. Indentation alone is ambiguous user text.
            if current and continuation_start.match(value):
                current = (current + " " + value)[:1200]
                continue

            # This includes all plain, numbered, and markdown section headings,
            # plus any prose or malformed citation that cannot be safely classified.
            break
    if current:
        entries.append(current)
    result = []
    for idx, entry in enumerate(entries):
        doi_match = re.search(
            r"(?i)\b(?:https?://doi\.org/)?(10\.\d{4,9}/[A-Za-z0-9._;()/:+-]{1,180})\b",
            entry,
        )
        doi = doi_match.group(1).rstrip(".,)") if doi_match else None
        year_match = re.search(r"\b(1[4-9]\d{2}|20\d{2}|21\d{2}|2200)\b", entry)
        year = int(year_match.group(1)) if year_match else None
        # Queries contain only citation fields from the accepted section.
        authors: tuple[str, ...] = ()
        title = ""
        if section_name == "learning_resources":
            clean_entry = re.sub(r"https?://\S+", "", entry).strip()
            editor_marker = re.search(r"\(Eds?\)\.?\s*", clean_entry, re.I)
            boundary = re.search(r"\.\s+", clean_entry)
            if editor_marker:
                author_text = clean_entry[: editor_marker.end()].strip(" .")
                title_start = editor_marker.end()
            elif boundary:
                author_text = clean_entry[: boundary.start()].strip()
                title_start = boundary.end()
            else:
                author_text, title_start = "", len(clean_entry)
            title_tail = clean_entry[title_start:]
            title_tail = re.split(
                r"\b(?:1[4-9]\d{2}|20\d{2}|21\d{2}|2200)\b",
                title_tail,
                maxsplit=1,
            )[0]
            title_tail = re.sub(
                r"\s+\d+(?:st|nd|rd|th)\s+edition\b.*$",
                "",
                title_tail,
                flags=re.I,
            )
            title = re.split(r"\.\s+(?=[A-Z])", title_tail, maxsplit=1)[0].strip(
                " .\"'“”"
            )
            private_metadata = re.compile(
                r"(?i)\b(?:student|learner|faculty|email|phone|mobile|address|"
                r"confidential|private|prepared\s+by|student\s*id|id\s*(?:no|number))\b"
            )
            author_identifiable = bool(
                len(author_text) <= 100
                and not private_metadata.search(author_text)
                and (
                    "," in author_text
                    or "&" in author_text
                    or re.search(r"\band\b", author_text, re.I)
                )
            )
            if (
                author_identifiable
                and len(re.findall(r"[A-Za-z]+", title)) >= 2
                and not re.search(
                    r"(?i)\b(?:university|pittsburgh|pennsylvania|copyright|retrieved|institute)\b",
                    title,
                )
            ):
                authors = (author_text,)
        else:
            title_match = re.search(
                r"\(?(?:1[4-9]\d{2}|20\d{2}|21\d{2}|2200)\)?[.,]?\s+([^.!?]{3,300})",
                entry,
            )
            if title_match:
                title = title_match.group(1).strip(" .\"'“”")
            author_match = re.match(
                r"^(.{3,180}?)\s+\(?(?:1[4-9]\d{2}|20\d{2}|21\d{2}|2200)\)?",
                entry,
            )
            if author_match and re.search(
                r"[A-Za-z][A-Za-z'-]{2,}", author_match.group(1)
            ):
                authors = (author_match.group(1).strip(),)
        identity = bool(authors)
        if title and re.search(
            r"(?i)\b(?:student|email|phone|address|prepared by)\b", title
        ):
            continue
        if not doi and (not identity or not title):
            continue
        fields = tuple(
            sorted(
                (["doi"] if doi else [])
                + (["title"] if title else [])
                + (["author"] if authors else [])
                + (["year"] if year else [])
            )
        )
        try:
            ref = PublicReference(
                source_id=f"ref-{idx + 1}",
                visibility="user_approved_public",
                origin="approved_reference_inventory",
                tags=fields,
                doi=doi,
                title=title or None,
                authors=authors,
                year=year,
            )
        except ValueError:
            continue
        safe_query = " ".join(
            part
            for part in (
                title,
                " ".join(authors),
                doi,
                str(year) if year else "",
            )
            if part
        )
        result.append(BibliographyItem(ref, safe_query, citation_section=section_name))
    return tuple(result)


def extract_public_topics(text: str) -> tuple[BibliographyItem, ...]:
    """Extract short topic names from the module metadata header only."""
    header_end = re.search(
        r"(?i)\b(?:description(?:\s+of\s+the\s+lesson)?|learning\s+outcomes?|"
        r"targets?|objectives?|assessment|student\s+(?:records?|details?)|"
        r"discussion|references|bibliography)\b",
        text[:BIBLIOGRAPHY_CHARACTER_LIMIT],
    )
    header = text[: header_end.start() if header_end else BIBLIOGRAPHY_CHARACTER_LIMIT]
    labels = re.compile(
        r"(?<![A-Za-z])(?P<label>Lesson\s+Title|LESSON\s+TITLE|"
        r"Topic(?:\s+Title)?|TOPIC(?:\s+TITLE)?|Unit(?:\s+Title)?|UNIT(?:\s+TITLE)?)"
        r"(?![A-Za-z])(?:\s*[:\-–—]\s*|\s+(?=[A-Z])|\s*\n\s*)"
    )
    boundaries = re.compile(
        r"(?i)\b(?:week\s+duration|date|description(?:\s+of\s+the\s+lesson)?|"
        r"module\s+no\.?|course(?:\s+title)?|sem\s*/\s*ay|references|"
        r"learning\s+outcomes?|objectives?|assessment|materials?|name|"
        r"prepared\s+by|author|instructor|contact|email|phone)\b"
    )
    private = re.compile(
        r"(?i)(?:\b(?:student|learner|faculty|email|phone|mobile|address|"
        r"student\s*id|id\s*(?:no|number))\b|@|\b\d{4,}\b|"
        r"\b(?:19|20|21)\d{2}\b|\+\d|\d{3}[-.) ]\d{3}[-. ]\d{4})"
    )
    topics: list[BibliographyItem] = []
    seen: set[str] = set()
    for match in labels.finditer(header):
        label = match.group("label")
        marked = bool(
            re.search(r"[:\-–—]\s*$", match.group(0)) or "\n" in match.group(0)
        )
        prefix = header[: match.start()]
        line_prefix = prefix.rsplit("\n", 1)[-1]
        standalone = not line_prefix.strip()
        lesson_title = label.casefold() == "lesson title" or label == "LESSON TITLE"
        recognized_flat_header = bool(
            lesson_title
            and re.match(r"(?i)^\s*(?:course(?:\s+title)?|module\s+no\.?)\b", prefix)
        )
        if lesson_title:
            if not (standalone or recognized_flat_header):
                continue
        elif not (standalone and marked):
            continue
        start = match.end()
        end = boundaries.search(header, start)
        candidate_end = end.start() if end else min(len(header), start + 160)
        unknown_metadata = re.search(
            r"(?<![A-Za-z])(?:[A-Z][A-Za-z /_-]{1,31}):\s*", header[start:candidate_end]
        )
        if unknown_metadata:
            candidate_end = min(
                candidate_end,
                start + unknown_metadata.start(),
            )
        candidate = header[start:candidate_end]
        # When the label occupies its own line, use only the next line as value.
        if not candidate.strip() and start < len(header):
            newline = header.find("\n", start)
            if newline >= 0:
                next_end = header.find("\n", newline + 1)
                candidate = header[
                    newline + 1 : next_end if next_end >= 0 else len(header)
                ]
        candidate = re.split(r"[.;\n]", candidate, maxsplit=1)[0]
        value = " ".join(candidate.split()).strip(" :-–—,\t")
        words = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", value)
        if (
            not value
            or len(value) > 120
            or not 1 <= len(words) <= 12
            or private.search(value)
            or len("".join(words)) < 4
        ):
            continue
        normalized = " ".join(words).casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        title = " ".join(words)
        try:
            ref = PublicReference(
                source_id=f"topic-{len(topics) + 1}",
                visibility="user_approved_public",
                origin="approved_reference_inventory",
                tags=("title",),
                title=title,
            )
        except ValueError:
            continue
        topics.append(BibliographyItem(ref, title, "topic"))
        if len(topics) == 2:
            break
    return tuple(topics)


def readiness_config(
    settings: Any, *, enabled: bool, needs_search: bool = False
) -> dict[str, Any]:
    """Pure readiness seam; no settings lookup or network activity."""
    configured = bool(getattr(settings, "itso_verification_enabled", False))
    if not enabled or not configured:
        return {"ready": False, "reason": Code.DISABLED.value}
    return {"ready": True, "reason": None}


class ReferenceToolsUnavailable(RuntimeError):
    """Safe readiness failure carrying only a stable code."""

    def __init__(self, code: Code):
        self.code = code
        super().__init__(code.value)


class NoQueryableReferencesError(RuntimeError):
    """No safe bibliography reference or labelled lesson topic can be searched."""

    code = "no_queryable_public_references"

    def __init__(self) -> None:
        super().__init__(
            "No safely queryable public bibliography references or labelled "
            "lesson topics were found."
        )


def ensure_public_reference_tools_ready(
    *, settings: Any = None, needs_search: bool = True
) -> None:
    if settings is None:
        from ....core.config import get_settings

        settings = get_settings()
    result = readiness_config(settings, enabled=True, needs_search=needs_search)
    if not result["ready"]:
        raise ReferenceToolsUnavailable(Code(result["reason"]))


def _status_for_error(error: VerificationError) -> str:
    if error.code in {
        Code.SECURITY,
        Code.INVALID,
        Code.ACCESS,
        Code.HTTP,
        Code.LIMIT,
        Code.MALFORMED,
        Code.ROBOTS,
    }:
        return "unavailable"
    raise error


def _relevant_excerpt(paragraphs: list[str], title: str) -> str:
    stop = {"the", "a", "an", "of", "for", "and", "in", "on", "to", "with"}
    terms = {
        value
        for value in re.findall(r"[a-z0-9]+", title.casefold())
        if len(value) >= 4 and value not in stop
    }
    if not terms:
        return ""
    for paragraph in paragraphs:
        words = re.findall(r"[A-Za-z0-9]+", paragraph)
        if (
            len(paragraph) < 60
            or len(words) < 8
            or not re.search(r"[.!?](?:\s|$)", paragraph)
        ):
            continue
        word_set = {word.casefold() for word in words}
        if len(terms & word_set) >= max(1, (len(terms) + 1) // 2):
            return paragraph[:700]
    return ""


def _title_matches(reference_title: str, page_title: str) -> bool:
    stop = {"the", "a", "an", "of", "for", "and", "in", "on", "to", "with"}
    terms = {
        value
        for value in re.findall(r"[a-z0-9]+", reference_title.casefold())
        if len(value) >= 4 and value not in stop
    }
    page_words = set(re.findall(r"[a-z0-9]+", page_title.casefold()))
    return bool(terms) and terms <= page_words


def _topic_title_matches(topic: str, page_title: str) -> bool:
    stop = {"the", "a", "an", "of", "for", "and", "in", "on", "to", "with"}
    expected = {
        value
        for value in re.findall(r"[a-z0-9]+", topic.casefold())
        if len(value) >= 4 and value not in stop
    }
    actual = set(re.findall(r"[a-z0-9]+", page_title.casefold()))
    overlap = len(expected & actual)
    return (
        bool(expected)
        and overlap >= min(2, len(expected))
        and (overlap / len(expected) >= 0.45)
    )


def _url_identity(url: str) -> dict[str, str]:
    """Keep source-attempt identity bounded without repeating long URLs."""
    return {
        "host": urlsplit(url).hostname or "",
        "url_hash": hashlib.sha256(url.encode("ascii")).hexdigest(),
    }


async def build_public_reference_report(
    query_text: str,
    *,
    enabled: bool,
    settings: Any = None,
    transport: Transport | None = None,
    clock=time.monotonic,
) -> dict[str, Any]:
    """Search and inspect public sources for references or labelled topics.

    Disabled calls remain available for legacy/internal compatibility. Current
    adapter-3 execution always enables this report.
    """
    if settings is None:
        from ....core.config import get_settings

        settings = get_settings()
    if not enabled:
        return {
            "status": "disabled",
            "scope": list(SCOPE),
            "references": [],
            "coverage": {"found": 0, "checked": 0, "skipped": 0, "total": 0},
            "limits": {"reference_cap": REFERENCE_LIMIT},
        }
    ensure_public_reference_tools_ready(settings=settings, needs_search=True)
    bibliography_items = extract_bibliography(query_text)
    bibliography_status = "found" if bibliography_items else "not_detected"
    items = bibliography_items or extract_public_topics(query_text)
    if not items:
        raise NoQueryableReferencesError()
    transport = transport or PinnedHTTPS()
    deadline = clock() + TOTAL_DEADLINE_SECONDS
    output = []
    search_attempts = 0
    source_attempts = 0
    for item in items[:REFERENCE_LIMIT]:
        ref = item.reference
        row: dict[str, Any] = {
            "query": item.query,
            "query_kind": item.query_kind,
            "bibliography_status": bibliography_status,
            "status": "unverified",
            "source_url": None,
            "title": None,
            "excerpt": None,
            "matched_fields": [],
            "mismatches": [],
            "registry_status": "not_applicable"
            if item.query_kind == "topic"
            else "not_checked",
            "registry_url": None,
            "registry_title": None,
            "registry_matched_fields": [],
            "registry_mismatches": [],
            "source_attempts": [],
            "search_attempts": [],
        }
        if (
            item.query_kind == "bibliography"
            and item.citation_section == "learning_resources"
        ):
            row["cited_reference"] = {
                "section": item.citation_section,
                "title": ref.title,
                "authors": list(ref.authors),
                "year": ref.year,
                "doi": ref.doi,
            }
        metadata = None
        if ref.doi:
            for provider in ("crossref", "datacite"):
                url = doi_url(provider, ref.doi)
                try:
                    response = await asyncio.wait_for(
                        transport.get(
                            Request(url, provider),
                            min(deadline, clock() + CALL_DEADLINE_SECONDS),
                        ),
                        max(
                            0.001,
                            min(deadline, clock() + CALL_DEADLINE_SECONDS) - clock(),
                        ),
                    )
                    if response.status == 404:
                        continue
                    if response.status != 200:
                        raise VerificationError(Code.HTTP)
                    metadata = (
                        parse_crossref if provider == "crossref" else parse_datacite
                    )(response.body)
                    row["registry_url"] = url
                    break
                except TimeoutError:
                    raise VerificationError(Code.DEADLINE) from None
        if metadata:
            status, matched, mismatch = match_metadata(ref, metadata)
            row["registry_status"] = status
            row["registry_title"] = metadata.title
            row["status"] = "unverified"
            row["matched_fields"] = list(matched)
            row["mismatches"] = list(mismatch)
            row["registry_matched_fields"] = list(matched)
            row["registry_mismatches"] = list(mismatch)
        search_ref = ref
        if metadata and not ref.title:
            tags = tuple(
                sorted(
                    ["title"]
                    + (["doi"] if ref.doi else [])
                    + (["year"] if ref.year else [])
                )
            )
            search_ref = PublicReference(
                source_id=ref.source_id,
                visibility="user_approved_public",
                origin="approved_reference_inventory",
                tags=tags,
                doi=ref.doi,
                title=metadata.title,
                year=ref.year,
            )
        search_refs = [(search_ref, "primary")]
        title = search_ref.title
        if item.query_kind == "bibliography" and title:
            title_ref = PublicReference(
                source_id=search_ref.source_id,
                visibility="user_approved_public",
                origin="approved_reference_inventory",
                tags=("title",),
                title=title,
            )
            # DOI-only citations can acquire a registry title. Skip a duplicate
            # retry when the primary query already contains only that title.
            if duckduckgo_url(title_ref) != duckduckgo_url(search_ref):
                search_refs.append((title_ref, "title_only"))
        row["search_attempts"] = []
        usable_page_found = False
        seen_candidate_urls: set[str] = set()
        for current_search_ref, query_scope in search_refs:
            candidates = []
            try:
                search_attempts += 1
                search_url = duckduckgo_url(current_search_ref)
                response = await asyncio.wait_for(
                    transport.get(
                        Request(search_url, "duckduckgo"),
                        min(deadline, clock() + CALL_DEADLINE_SECONDS),
                    ),
                    max(
                        0.001, min(deadline, clock() + CALL_DEADLINE_SECONDS) - clock()
                    ),
                )
                if response.status != 200:
                    raise VerificationError(Code.HTTP)
                candidates = list(
                    parse_duckduckgo(
                        response.body,
                        current_search_ref,
                        candidate_limit=SOURCE_CANDIDATE_LIMIT,
                    )
                )
                row["search_attempts"].append(
                    {
                        "query_scope": query_scope,
                        "candidate_count": len(candidates),
                        "outcome": "candidates" if candidates else "no_candidates",
                    }
                )
            except VerificationError as exc:
                row["search_attempts"].append(
                    {
                        "query_scope": query_scope,
                        "candidate_count": 0,
                        "outcome": "error",
                        "error_code": exc.code.value,
                    }
                )
                raise
            except TimeoutError:
                row["search_attempts"].append(
                    {
                        "query_scope": query_scope,
                        "candidate_count": 0,
                        "outcome": "error",
                        "error_code": Code.DEADLINE.value,
                    }
                )
                raise VerificationError(Code.DEADLINE) from None
            for candidate in candidates[:SOURCE_CANDIDATE_LIMIT]:
                if candidate.url in seen_candidate_urls:
                    continue
                seen_candidate_urls.add(candidate.url)
                attempt: dict[str, Any] = {
                    "candidate_host": urlsplit(candidate.url).hostname or "",
                    "candidate_url_hash": hashlib.sha256(
                        candidate.url.encode("ascii")
                    ).hexdigest(),
                    "outcome": "unavailable",
                    "reason": "unavailable",
                }
                row["source_attempts"].append(attempt)
                try:
                    current_url = candidate.url
                    visited_urls: set[str] = set()
                    redirects = 0
                    while True:
                        validate_url(current_url)
                        validated = _url_identity(current_url)
                        if current_url != candidate.url:
                            attempt["validated_host"] = validated["host"]
                            attempt["validated_url_hash"] = validated["url_hash"]
                        if current_url in visited_urls:
                            raise VerificationError(Code.SECURITY)
                        visited_urls.add(current_url)
                        source_attempts += 1
                        page = await asyncio.wait_for(
                            transport.get(
                                Request(current_url, "document"),
                                min(deadline, clock() + CALL_DEADLINE_SECONDS),
                            ),
                            max(
                                0.001,
                                min(deadline, clock() + CALL_DEADLINE_SECONDS)
                                - clock(),
                            ),
                        )
                        if page.status not in {301, 302, 303, 307, 308}:
                            break
                        location = page.headers.get("location")
                        if not location:
                            attempt.update(
                                outcome="unavailable",
                                reason="redirect_missing_location",
                                http_status=page.status,
                            )
                            break
                        if redirects >= SOURCE_REDIRECT_LIMIT:
                            attempt.update(
                                outcome="unavailable",
                                reason="redirect_limit",
                                http_status=page.status,
                            )
                            break
                        current_url = urljoin(current_url, location)
                        validate_url(current_url)
                        redirects += 1
                    if page.status != 200:
                        row["status"] = "unavailable"
                        if attempt["reason"] not in {
                            "redirect_limit",
                            "redirect_missing_location",
                        }:
                            attempt.update(
                                outcome="unavailable",
                                reason="http_error",
                                http_status=page.status,
                            )
                        continue
                    parser = _PageParser()
                    parser.feed(page.body.decode("utf-8", "replace"))
                    title = " ".join(parser.title_parts)[:300]
                    parser._flush_block()
                    expected_title = ref.title or (metadata.title if metadata else "")
                    excerpt = _relevant_excerpt(parser.body_parts, expected_title)
                    title_match = (
                        _topic_title_matches(expected_title, title)
                        if item.query_kind == "topic"
                        else _title_matches(expected_title, title)
                    )
                    attempt.update(http_status=page.status)
                    if excerpt and title_match:
                        attempt.update(outcome="matched", reason="matched")
                    elif not title_match:
                        attempt.update(outcome="unmatched", reason="title_mismatch")
                    else:
                        attempt.update(
                            outcome="unmatched", reason="no_substantive_passage"
                        )
                    if excerpt:
                        row.update(
                            source_url=current_url, title=title or None, excerpt=excerpt
                        )
                    if excerpt and title_match:
                        usable_page_found = True
                        # Page resemblance supplements a clean registry result or
                        # provides a title-only match; it never clears a conflict.
                        if row["registry_status"] in {
                            "not_applicable",
                            "not_checked",
                            "matched",
                        }:
                            match_field = (
                                "topic" if item.query_kind == "topic" else "page_title"
                            )
                            if match_field not in row["matched_fields"]:
                                row["matched_fields"].append(match_field)
                            if item.citation_section == "learning_resources":
                                unverified = [
                                    field
                                    for field, present in (
                                        ("author", bool(ref.authors)),
                                        ("year", ref.year is not None),
                                    )
                                    if present
                                    and field not in row["registry_matched_fields"]
                                ]
                                if unverified:
                                    row["unverified_fields"] = unverified
                                    row["status"] = "ambiguous"
                                else:
                                    row["status"] = "matched"
                            else:
                                row["status"] = "matched"
                            break
                        elif row["registry_status"] == "ambiguous":
                            row["status"] = "ambiguous"
                            break
                        elif row["registry_status"] == "mismatched":
                            row["status"] = "mismatched"
                            break
                    elif row["status"] == "unverified":
                        row["status"] = "unverified"
                except VerificationError as exc:
                    attempt.update(
                        outcome="unavailable",
                        reason=exc.code.value,
                        error_code=exc.code.value,
                    )
                    if exc.code == Code.DEADLINE:
                        if clock() >= deadline:
                            raise
                        row["status"] = "unavailable"
                    else:
                        row["status"] = _status_for_error(exc)
                except TimeoutError:
                    attempt.update(
                        outcome="unavailable",
                        reason="timeout",
                        error_code=Code.DEADLINE.value,
                    )
                    if clock() >= deadline:
                        raise VerificationError(Code.DEADLINE) from None
                    row["status"] = "unavailable"
            if usable_page_found:
                break
        output.append(row)
    total = len(bibliography_items)
    topic_total = len(items) if not bibliography_items else 0
    report = {
        "status": "completed",
        "provider": "duckduckgo_html",
        "bibliography_status": bibliography_status,
        **(
            {
                "reference_sections": sorted(
                    {item.citation_section for item in bibliography_items}
                )
            }
            if bibliography_items
            else {}
        ),
        "attempts": {"search": search_attempts, "source": source_attempts},
        "scope": list(SCOPE),
        "references": output,
        "coverage": {
            "found": len(bibliography_items),
            "checked": len(output) if bibliography_items else 0,
            "skipped": max(0, total - len(output)),
            "total": total,
            **(
                {
                    "topic_queries": {
                        "found": topic_total,
                        "checked": len(output),
                        "skipped": max(0, topic_total - len(output)),
                        "total": topic_total,
                    }
                }
                if topic_total
                else {}
            ),
        },
        "limits": {
            "reference_cap": REFERENCE_LIMIT,
            "deadline_seconds": TOTAL_DEADLINE_SECONDS,
            "excerpt_characters": 700,
            "source_candidate_cap": SOURCE_CANDIDATE_LIMIT,
            "source_redirect_cap": SOURCE_REDIRECT_LIMIT,
            "source_response_bytes": DOCUMENT_LIMIT,
            "provider_response_bytes": LIMIT,
        },
        "source_attempt_identities_omitted": False,
        "source_attempt_details_omitted": False,
    }
    if len(json.dumps(report, sort_keys=True)) > 24_000:
        for row in output:
            for attempt in row["source_attempts"]:
                for key in (
                    "candidate_host",
                    "candidate_url_hash",
                    "validated_host",
                    "validated_url_hash",
                ):
                    attempt.pop(key, None)
        report["source_attempt_identities_omitted"] = True
    if len(json.dumps(report, sort_keys=True)) > 24_000:
        for row in output:
            grouped: dict[tuple[Any, ...], int] = {}
            for attempt in row.pop("source_attempts"):
                signature = (
                    attempt["outcome"],
                    attempt["reason"],
                    attempt.get("error_code"),
                    attempt.get("http_status"),
                )
                grouped[signature] = grouped.get(signature, 0) + 1
            row["source_attempt_summary"] = [
                {
                    "outcome": outcome,
                    "reason": reason,
                    **({"error_code": error_code} if error_code else {}),
                    **({"http_status": http_status} if http_status else {}),
                    "count": count,
                }
                for (outcome, reason, error_code, http_status), count in sorted(
                    grouped.items(), key=lambda entry: str(entry[0])
                )
            ]
        report["source_attempt_details_omitted"] = True
    if len(json.dumps(report, sort_keys=True)) > 24_000:
        # New recovery diagnostics are optional. Preserve citation identity and
        # fetched source passages before applying the existing receipt budget.
        for row in output:
            row.pop("search_attempts", None)
        report["search_attempt_details_omitted"] = True
    if len(json.dumps(report, sort_keys=True)) > 24_000:
        for row in output:
            row.pop("excerpt", None)
    return report
