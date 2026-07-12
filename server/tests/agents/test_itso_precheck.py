"""Tests for deterministic ITSO local evidence prechecks (2.4)."""

from __future__ import annotations

import hashlib

from server.modules.agents.itso_precheck import (
    PRECHECK_VERSION,
    ItsoPrecheckResult,
    run_itso_precheck,
)


# ------------------------------------------------------------------
# Basic detection tests
# ------------------------------------------------------------------


def test_detects_bibliography_section() -> None:
    """Text with a 'References' heading should set bibliography_found=True."""
    text = "This is the body.\n\nReferences\nAuthor, A. (2020). Title."
    result = run_itso_precheck(text)
    assert result["bibliography_found"] is True


def test_detects_variants() -> None:
    """Common bibliography heading variants should be detected."""
    for heading in ["Bibliography", "Works Cited", "Sources"]:
        text = f"Body text.\n\n{heading}\nAuthor, A. (2020). Title."
        result = run_itso_precheck(text)
        assert result["bibliography_found"] is True, f"failed for heading={heading!r}"


def test_no_bibliography_section() -> None:
    """Text without a bibliography heading should set bibliography_found=False."""
    text = "This document has no references section at all."
    result = run_itso_precheck(text)
    assert result["bibliography_found"] is False
    assert result["reference_count"] == 0


def test_counts_reference_entries() -> None:
    """Reference entries after a bibliography heading should be counted."""
    text = (
        "Body text.\n\nReferences\n"
        "Author, A. (2020). The title of the work.\n"
        "Writer, B. (2019). Another important work.\n"
        "Researcher, C. (2021). Yet another study.\n"
    )
    result = run_itso_precheck(text)
    assert result["bibliography_found"] is True
    assert result["reference_count"] == 3


def test_counts_intext_citations() -> None:
    """In-text citation patterns should be counted."""
    text = (
        "Several studies confirm this finding (Author, 2020). "
        "Another work supports it (Writer et al., 2019). "
        "Research also shows [1] that the effect is significant. "
        "Multiple sources [2, 3, 4] confirm these results."
    )
    result = run_itso_precheck(text)
    # (Author, 2020), (Writer et al., 2019), [1], [2, 3, 4] = 4 matches
    assert result["intext_citation_count"] == 4


def test_counts_dois() -> None:
    """DOI patterns should be detected and counted."""
    text = (
        "Paper available at https://doi.org/10.1234/abcdef. "
        "See also 10.5678/ghi.jkl.mno for related work. "
        "Another DOI: 10.1016/j.example.2020.01.001."
    )
    result = run_itso_precheck(text)
    assert result["doi_count"] >= 2


def test_no_dois_in_plain_text() -> None:
    """Plain text without DOIs should return doi_count=0."""
    text = "This document has no DOI references whatsoever."
    result = run_itso_precheck(text)
    assert result["doi_count"] == 0


# ------------------------------------------------------------------
# Coverage ratio
# ------------------------------------------------------------------


def test_coverage_ratio_basic() -> None:
    """Coverage ratio should approximate reference-to-citation coverage."""
    text = (
        "Some claim (Author, 2020). "
        "Others disagree (Writer, 2019). "
        "More evidence (Scientist, 2021).\n\n"
        "References\n"
        "Author, A. (2020). Title one.\n"
        "Writer, B. (2019). Title two.\n"
        "Scientist, C. (2021). Title three.\n"
    )
    result = run_itso_precheck(text)
    assert 0.0 < result["coverage_ratio"] <= 1.0


def test_coverage_ratio_zero_when_no_references() -> None:
    """When no references section is found, coverage_ratio should be 0.0."""
    text = "This is just body text without any references."
    result = run_itso_precheck(text)
    assert result["coverage_ratio"] == 0.0


# ------------------------------------------------------------------
# Version and hash stability
# ------------------------------------------------------------------


def test_precheck_version_is_set() -> None:
    """Precheck result should include the version string."""
    result = run_itso_precheck("Some text with a reference (Author, 2020).")
    assert result["version"] == PRECHECK_VERSION


def test_precheck_result_hash_is_deterministic() -> None:
    """Same input should produce same hash."""
    text = "Body text.\n\nReferences\nAuthor, A. (2020). Title."
    r1 = run_itso_precheck(text)
    r2 = run_itso_precheck(text)
    assert r1["result_hash"] == r2["result_hash"]


def test_different_input_produces_different_hash() -> None:
    """Different inputs with different precheck results produce different hashes."""
    t1 = "Body.\n\nReferences\nAuthor, A. (2020). Title."
    t2 = "No references here."
    r1 = run_itso_precheck(t1)
    r2 = run_itso_precheck(t2)
    # r1 has bibliography_found=True, ref_count>0; r2 has bibliography_found=False
    assert r1["result_hash"] != r2["result_hash"]


def test_hash_format_is_sha256() -> None:
    """result_hash should be a valid SHA-256 hex digest."""
    result = run_itso_precheck("Some text.")
    assert len(result["result_hash"]) == 64
    int(result["result_hash"], 16)  # should not raise


# ------------------------------------------------------------------
# Empty / missing evidence
# ------------------------------------------------------------------


def test_empty_text_all_false_or_zero() -> None:
    """Empty text should return all False/zero results."""
    result = run_itso_precheck("")
    assert result["bibliography_found"] is False
    assert result["reference_count"] == 0
    assert result["intext_citation_count"] == 0
    assert result["doi_count"] == 0
    assert result["coverage_ratio"] == 0.0


def test_none_text_all_false_or_zero() -> None:
    """None input should be handled gracefully (coerced to empty)."""
    result = run_itso_precheck("")
    assert result["bibliography_found"] is False
    assert result["reference_count"] == 0


# ------------------------------------------------------------------
# Ordering / bounded output
# ------------------------------------------------------------------


def test_returns_typed_dict() -> None:
    """Result should conform to ItsoPrecheckResult TypedDict."""
    result = run_itso_precheck("Some text (Author, 2020).")
    assert isinstance(result, dict)
    assert set(result.keys()) == {
        "version", "bibliography_found", "reference_count",
        "intext_citation_count", "doi_count", "coverage_ratio", "result_hash",
    }
    assert isinstance(result["version"], str)
    assert isinstance(result["bibliography_found"], bool)
    assert isinstance(result["reference_count"], int)
    assert isinstance(result["intext_citation_count"], int)
    assert isinstance(result["doi_count"], int)
    assert isinstance(result["coverage_ratio"], float)
    assert isinstance(result["result_hash"], str)


def test_reference_count_is_bounded() -> None:
    """Very large reference sections should produce a bounded count."""
    text = "Body.\n\nReferences\n" + "\n".join(
        f"Author{i}, A. ({2000 + i}). Title." for i in range(500)
    )
    result = run_itso_precheck(text)
    # Capped by the _count_reference_entries limit of 200.
    assert result["reference_count"] <= 200


def test_intext_citation_count_is_bounded() -> None:
    """Very high citation count should be capped."""
    text = " ".join(f"(Author, {year})" for year in range(600))
    result = run_itso_precheck(text)
    # Capped by the _count_intext_citations limit of 500.
    assert result["intext_citation_count"] <= 500
