"""Traceability and quotation requirements for ITSO document findings."""

from types import SimpleNamespace

import pytest
from equiped_harness.agents.itso.document_review import (
    review_chunks,
    review_coverage,
    unquoted_review_status,
    validate_review_evidence,
)
from equiped_harness.exceptions import AgentExecutionError


def test_mapping_cannot_override_authoritative_criterion_code():
    criteria = (SimpleNamespace(criterion_code="ITSO-03", scoring_rule="Defined"),)
    parsed = {
        "criterion_scores": {
            "ITSO-03": {
                "criterion_id": "ITSO-01",
                "score": 4,
                "evidence": [],
                "justification": "Ownership supported.",
            }
        }
    }
    with pytest.raises(AgentExecutionError, match="requires a quotation"):
        validate_review_evidence(parsed, criteria)


def test_numeric_mapping_cannot_bypass_quotation_requirement():
    criteria = (SimpleNamespace(criterion_code="ITSO-04", scoring_rule="Defined"),)
    for score in (2, 4):
        with pytest.raises(AgentExecutionError, match="reasoning is required"):
            validate_review_evidence({"criterion_scores": {"ITSO-04": score}}, criteria)


@pytest.mark.parametrize(
    "code,rule,score,expected",
    [
        ("ITSO-04", "Defined", 4, "no_concern_detected"),
        ("ITSO-05", "Defined", 3, "rights_unverified"),
        ("ITSO-04", "Defined", 3, None),
        ("ITSO-05", "Defined", 4, None),
        ("ITSO-04", None, 4, None),
        ("ITSO-05", "", 3, None),
        ("ITSO-03", "Defined", 3, None),
    ],
)
def test_unquoted_review_status_classifies_only_allowed_rule_scores(
    code, rule, score, expected
):
    criterion = SimpleNamespace(criterion_code=code, scoring_rule=rule)
    assert unquoted_review_status(criterion, score) == expected


def test_coverage_retains_real_ellipsis_and_rejects_non_source_text():
    chunks = [{"chunk_id": "c1", "text": "A real ellipsis..."}]
    context = SimpleNamespace(chunk_infos=chunks)
    coverage = review_coverage(context, chunks)
    assert coverage["all_supplied_text_reviewed"] is True
    assert coverage["reviewed_text_characters"] == len(chunks[0]["text"])
    with pytest.raises(AgentExecutionError, match="not supplied source"):
        review_coverage(context, [{"chunk_id": "c1", "text": "invented"}])


def test_authorship_clause_survives_dense_reference_list_and_prefix_clipping():
    authorship = "Prepared by: Faculty Author."
    references = "Learning resources. " + "author acknowledgement " * 30
    text = references + " Ordinary course material. " * 30 + authorship
    chunks = review_chunks(({"chunk_id": "c1", "text": text},), excerpt_chars=200)
    assert authorship in chunks[0]["text"]
    assert chunks[0]["text"] in text
    assert len(chunks[0]["text"]) <= 200


@pytest.mark.parametrize(
    "code,text",
    [
        ("ITSO-01", "An HCI lesson statement."),
        ("ITSO-02", "Learning resources: A textbook, 2020."),
        ("ITSO-03", "Prepared by: Faculty Author."),
    ],
)
def test_available_source_or_authorship_passage_requires_quote_even_for_three(
    code, text
):
    criteria = (SimpleNamespace(criterion_code=code, scoring_rule="Defined"),)
    parsed = {
        "criterion_scores": [
            {
                "criterion_id": code,
                "score": 3,
                "justification": "Scoped provisional assessment.",
                "evidence": [],
            }
        ]
    }
    with pytest.raises(AgentExecutionError, match="requires a quotation"):
        validate_review_evidence(parsed, criteria, packed_chunk_map={"c1": text})
    parsed["criterion_scores"][0]["evidence"] = [text]
    validate_review_evidence(parsed, criteria, packed_chunk_map={"c1": text})
