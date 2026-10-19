"""SME absence findings must not masquerade as source quotations."""

from __future__ import annotations

import json
import uuid

import pytest
from equiped_harness.contracts import CriterionDefinition, LlmRubricGuidanceConfig
from equiped_harness.exceptions import AgentExecutionError
from equiped_harness.sme.response import (
    build_envelope_schema,
    parse_and_validate_envelope_response,
)
from equiped_harness.sme.scoring import score_criterion_measurement
from jsonschema import Draft202012Validator

SOURCE = "This lesson introduces PHP variables and expressions."
REASON = "No enhancement activity was found in the supplied source text."


@pytest.fixture
def criterion():
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code="OP-05",
        title="Enhancement Activities",
        description="Enhancement activities are provided.",
        display_order=0,
        strategy_config=LlmRubricGuidanceConfig(
            guidance="Judge the enhancement activities beyond the core lesson."
        ),
    )


def payload(**changes):
    measurement = {
        "criterion_id": "OP-05",
        "criterion_title": "Enhancement Activities",
        "score": 1,
        "finding": "absent",
        "evidence": None,
        "reasoning": REASON,
        **changes,
    }
    return {
        "summary": "No enhancement activity found.",
        "criterion_measurements": [measurement],
    }


@pytest.mark.parametrize("score", [1, 2, 3, 4])
def test_absence_retains_rubric_score_without_fabricated_evidence(criterion, score):
    data = payload(score=score)
    Draft202012Validator(build_envelope_schema((criterion,))).validate(data)
    parsed = parse_and_validate_envelope_response(
        json.dumps(data), (criterion,), SOURCE
    )
    measurement = parsed["criterion_measurements"][0]
    result = score_criterion_measurement(criterion, measurement)

    assert measurement["finding"] == "absent"
    assert measurement["evidence"] is None
    assert result.score == score
    assert result.evidence == ()
    assert result.chunk_ids == ()
    assert result.justification == f"Not found in the supplied source text. {REASON}"


@pytest.mark.parametrize(
    "changes",
    [
        {"reasoning": None},
        {"reasoning": ""},
        {"reasoning": "   "},
        {"reasoning": " explanation "},
        {"reasoning": "Explanation with trailing newline.\n"},
        {"reasoning": "x" * 2001},
        {"evidence": "The module has no enhancement activities."},
        {"evidence": ""},
        {"finding": "unknown"},
        {"finding": None},
        {"finding": "present"},
    ],
)
def test_invalid_absence_cannot_bypass_evidence_contract(criterion, changes):
    assert not Draft202012Validator(build_envelope_schema((criterion,))).is_valid(
        payload(**changes)
    )
    with pytest.raises(AgentExecutionError):
        parse_and_validate_envelope_response(
            json.dumps(payload(**changes)), (criterion,), SOURCE
        )


def test_missing_quote_without_explicit_absence_is_rejected(criterion):
    data = payload()
    del data["criterion_measurements"][0]["finding"]
    with pytest.raises(AgentExecutionError):
        parse_and_validate_envelope_response(json.dumps(data), (criterion,), SOURCE)


@pytest.mark.parametrize("finding", [None, "present"])
def test_present_and_legacy_findings_still_require_verbatim_quotes(criterion, finding):
    data = payload(finding="present", evidence="This lesson introduces PHP variables")
    if finding is None:
        del data["criterion_measurements"][0]["finding"]
    Draft202012Validator(build_envelope_schema((criterion,))).validate(data)
    parsed = parse_and_validate_envelope_response(
        json.dumps(data), (criterion,), SOURCE
    )
    result = score_criterion_measurement(criterion, parsed["criterion_measurements"][0])
    assert result.evidence == ("This lesson introduces PHP variables",)
    assert result.justification == REASON

    data["criterion_measurements"][0]["evidence"] = "Invented quotation."
    with pytest.raises(AgentExecutionError, match="not an exact substring"):
        parse_and_validate_envelope_response(json.dumps(data), (criterion,), SOURCE)


def test_schema_rejects_quote_free_present_and_unexplained_absent_findings(criterion):
    validator = Draft202012Validator(build_envelope_schema((criterion,)))
    for data in (
        payload(finding="present"),
        payload(reasoning=None),
        payload(evidence=SOURCE),
    ):
        assert not validator.is_valid(data)
