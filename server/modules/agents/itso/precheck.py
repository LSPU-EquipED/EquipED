"""Deterministic local ITSO evidence prechecks.

Provides a pure, versioned function that scans SLM text for bibliography
presence, reference counts, in-text citation patterns, DOI candidates,
and a simple reference-to-citation coverage ratio.

All outputs are deterministic for the same input text. The function never
connects to external services and never makes plagiarism, legal, or
source-validity determinations.

Usage::

    result = run_itso_precheck(slm_text)
"""

from __future__ import annotations

import hashlib
import re
from typing import TypedDict

PRECHECK_VERSION = "1"

# ---------------------------------------------------------------------------
# Pattern definitions (versioned — change with care)
# ---------------------------------------------------------------------------

# Bibliography / references section headings (case-insensitive)
_BIBLIOGRAPHY_HEADING_RE = re.compile(
    r"(?:^|\n)\s*(?:references|bibliography|works\s+cited|sources)"
    r"\s*[:]?\s*(?:\n|$)",
    re.IGNORECASE,
)

# In-text citation patterns: author-year "(Author, YYYY)", numeric "[1]", and
# variations like "(Author et al., YYYY)" "(Author & Author, YYYY)".
_INTEXT_CITATION_RE = re.compile(
    r"(?:"  # author-year
    r"\([^)]*\b(?:19|20)\d{2}\b[^)]*\)"
    r"|"  # numeric
    r"\[\d+(?:\s*[-,]\s*\d+)*\]"
    r"|"  # superscript-style
    r"(?:^|\s)\[?\d+(?:\s*[-,]\s*\d+)*\]?(?=\s|$|\.|,)"
    r")",
    re.IGNORECASE,
)

# Candidate DOI references.
_DOI_RE = re.compile(
    r"\b10\.\d{4,}(?:\.\d+)*/[-._;()/:a-zA-Z0-9]+\b",
)

# Per-line bibliography entry heuristic: line starts with author name /
# title-like text optionally preceded by a number or bullet.
_LINE_SPLIT_RE = re.compile(r"\n+")
_BIBLIO_ENTRY_RE = re.compile(r"^\s*(?:\d+[.)]\s*)?[A-Z][A-Za-z0-9\s,.'()/-]+[.?!]$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ItsoPrecheckResult(TypedDict):
    """Stable, bounded precheck output for ITSO evidence context.

    All fields are deterministic for the same ``text`` input.
    ``result_hash`` covers the canonical serialization of every other field.
    """

    version: str
    bibliography_found: bool
    reference_count: int
    intext_citation_count: int
    doi_count: int
    coverage_ratio: float
    result_hash: str


def run_itso_precheck(text: str) -> ItsoPrecheckResult:
    """Run deterministic local prechecks on SLM text.

    Parameters
    ----------
    text:
        The SLM evidence text (bounded by the prompt budget; typically a
        subset of the full document).

    Returns
    -------
    ItsoPrecheckResult
        Stable precheck signals. Never contains raw SLM text.
    """
    bibliography_found = _detect_bibliography_section(text)
    reference_count = _count_reference_entries(text) if bibliography_found else 0
    intext_citation_count = _count_intext_citations(text)
    doi_count = _count_dois(text)

    # Coverage ratio: how many references have at least one in-text
    # citation pointing to them. When no references are found, ratio is 0.0.
    coverage_ratio = _compute_coverage_ratio(text)

    # Build a stable, ordered representation for hashing.
    canonical = _build_canonical(
        version=PRECHECK_VERSION,
        bibliography_found=bibliography_found,
        reference_count=reference_count,
        intext_citation_count=intext_citation_count,
        doi_count=doi_count,
        coverage_ratio=coverage_ratio,
    )
    result_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return ItsoPrecheckResult(
        version=PRECHECK_VERSION,
        bibliography_found=bibliography_found,
        reference_count=reference_count,
        intext_citation_count=intext_citation_count,
        doi_count=doi_count,
        coverage_ratio=coverage_ratio,
        result_hash=result_hash,
    )


# ---------------------------------------------------------------------------
# Internal helpers (pure, deterministic)
# ---------------------------------------------------------------------------


def _detect_bibliography_section(text: str) -> bool:
    """Return ``True`` if text contains a bibliography/references heading."""
    return bool(_BIBLIOGRAPHY_HEADING_RE.search(text or ""))


def _count_reference_entries(text: str) -> int:
    """Count candidate reference entries in the bibliography section.

    Uses a simple heuristic: lines in the detected bibliography section
    that match a candidate entry pattern. Returns 0 if no bibliography
    section is detected.
    """
    match = _BIBLIOGRAPHY_HEADING_RE.search(text or "")
    if not match:
        return 0

    # Everything after the heading.
    after_heading = text[match.end() :]
    # Take at most the first 200 lines (bounded).
    lines = _LINE_SPLIT_RE.split(after_heading)[:200]
    count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Stop at the next section heading (all-caps or title-case heading).
        if re.match(
            r"^(?:[A-Z][A-Z\s]+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*:?\s*$", stripped
        ):
            break
        if _BIBLIO_ENTRY_RE.match(stripped):
            count += 1
    # Cap to a reasonable maximum to prevent unbounded output.
    return min(count, 200)


def _count_intext_citations(text: str) -> int:
    """Count candidate in-text citation patterns."""
    if not text:
        return 0
    matches = _INTEXT_CITATION_RE.findall(text)
    # Cap to prevent unbounded output.
    return min(len(matches), 500)


def _count_dois(text: str) -> int:
    """Count candidate DOI patterns."""
    if not text:
        return 0
    matches = _DOI_RE.findall(text)
    return min(len(matches), 100)


def _compute_coverage_ratio(text: str) -> float:
    """Estimate what fraction of references have a companion in-text citation.

    This is a simple heuristic — it counts approximate reference entries
    and approximate in-text citations, then computes a bounded ratio.
    When no references are found, returns 0.0.
    """
    ref_count = _count_reference_entries(text)
    if ref_count == 0:
        return 0.0
    cit_count = _count_intext_citations(text)
    # Bounded: ratio cannot exceed 1.0.
    ratio = cit_count / ref_count
    return min(ratio, 1.0)


def _build_canonical(
    version: str,
    bibliography_found: bool,
    reference_count: int,
    intext_citation_count: int,
    doi_count: int,
    coverage_ratio: float,
) -> str:
    """Build a deterministic canonical string for hashing.

    Fields are serialized in a fixed order with stable formatting.
    """
    parts = [
        f"version={version}",
        f"bibliography_found={str(bibliography_found).lower()}",
        f"reference_count={reference_count}",
        f"intext_citation_count={intext_citation_count}",
        f"doi_count={doi_count}",
        f"coverage_ratio={coverage_ratio:.6f}",
    ]
    return "|".join(parts)


__all__ = [
    "ItsoPrecheckResult",
    "PRECHECK_VERSION",
    "run_itso_precheck",
]
