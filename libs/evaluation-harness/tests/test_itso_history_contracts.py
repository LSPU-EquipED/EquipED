"""Historical ITSO snapshot hashes and stored-result validation remain stable."""

import pytest
from equiped_harness.agents.itso.compatibility.contracts import (
    ITSO_CRITERION_IDS,
    CanonicalSourceSnapshot,
    CriterionAssessment,
    EvidenceFact,
    ITSOAssessmentResult,
    SourceSpan,
    build_source_snapshot,
    text_hash,
)
from pydantic import ValidationError

TEXT = "Cover\nReferences\n[1] A work (2024)\nFaculty ownership instrument\n"


def source(text=TEXT):
    return build_source_snapshot(
        "source-1",
        text,
        ((1, 0, len(text)),),
        "extractor-1",
        raw_pdf_hash=text_hash("synthetic-pdf-bytes"),
    )


def test_full_source_candidate_scan_is_not_complete_bibliography_claim():
    snapshot = source()
    assert snapshot.source_hash == text_hash(TEXT)
    assert snapshot.scan_complete and not snapshot.inventory_complete
    assert len(snapshot.references) == 1
    assert snapshot.inventory_uncertainties


@pytest.mark.parametrize(
    "change",
    [
        {"source_hash": "f" * 64},
        {"pages": ()},
        {
            "pages": (
                {
                    "page_number": 2,
                    "start_offset": 0,
                    "end_offset": len(TEXT),
                    "text_hash": text_hash(TEXT),
                },
            )
        },
        {
            "pages": (
                {
                    "page_number": 1,
                    "start_offset": 0,
                    "end_offset": len(TEXT),
                    "text_hash": "f" * 64,
                },
            )
        },
        {
            "pages": (
                {
                    "page_number": 1,
                    "start_offset": 1,
                    "end_offset": len(TEXT),
                    "text_hash": text_hash(TEXT[1:]),
                },
            )
        },
        {
            "references": (
                {
                    "reference_id": "r",
                    "start_offset": 10,
                    "end_offset": 1,
                    "text_hash": "f" * 64,
                },
            )
        },
    ],
)
def test_rejects_forged_or_incomplete_source_identity(change):
    payload = source().model_dump()
    payload.update(change)
    with pytest.raises(ValidationError):
        CanonicalSourceSnapshot.model_validate(payload)


def test_blank_pages_and_source_overflow_are_preserved():
    snapshot = build_source_snapshot(
        "source", "one\n\nthree", ((1, 0, 3), (2, 3, 3), (3, 5, 10)), "v1"
    )
    assert len(snapshot.pages) == 3
    assert snapshot.pages[1].warnings == ("blank_or_no_canonical_text",)
    with pytest.raises(ValueError, match="complete-scan bound"):
        source("x" * 200_001)


def test_spans_validate_hash_quote_id_and_page_not_semantic_truth():
    snapshot = source()
    span = SourceSpan(
        source_id="source-1",
        start_offset=0,
        end_offset=5,
        page_number=1,
        text_hash=text_hash("Cover"),
    )
    snapshot.validate_span(span, "Cover")
    with pytest.raises(ValueError):
        snapshot.validate_span(span, "Cover proves ownership")
    with pytest.raises(ValidationError):
        EvidenceFact(
            fact_id="f",
            predicate="actual_student",
            value="true",
            authority="verified_mechanical",
            source_spans=(span,),
            origin="regex",
            method_version="pii-substring.v1",
        )


def test_result_mean_only_when_five_exact_integer_scores_exist():
    rows = tuple(
        CriterionAssessment(
            criterion_id=c,
            applicability="applicable",
            evidence_state="observed",
            verification="unverified",
            score=s,
            rule_version="historical.v1",
        )
        for c, s in zip(ITSO_CRITERION_IDS, (1, 2, 3, 4, 4), strict=True)
    )
    kwargs = dict(
        evaluation_id="e",
        document_id="d",
        source_hash="a" * 64,
        raw_pdf_hash=text_hash("synthetic-pdf-bytes"),
        execution_status="COMPLETED",
        scoring_complete=True,
        criteria=rows,
    )
    assert ITSOAssessmentResult(**kwargs, subtotal=2.8).subtotal == 2.8
    for subtotal in (14, None, 2):
        with pytest.raises(ValidationError):
            ITSOAssessmentResult(**kwargs, subtotal=subtotal)
