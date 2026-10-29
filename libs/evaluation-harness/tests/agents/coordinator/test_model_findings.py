import pytest
from equiped_harness.agents.coordinator import model_findings as module
from equiped_harness.exceptions import AgentExecutionError


def test_finding_validator_preserves_frozen_identity_and_exact_model_text():
    text = (
        "The plan uses supervised practice in each listed unit. "
        "Evidence is present in reviewed items."
    )
    data = module.validate_finding_response(
        {"results": [{"criterion_id": "A-01", "score": 3, "finding": text}]},
        "A-01",
        3,
    )
    assert data["results"][0]["finding"] == text
    for row in (
        {"criterion_id": "A-02", "score": 3, "finding": text},
        {"criterion_id": "A-01", "score": 4, "finding": text},
    ):
        with pytest.raises(AgentExecutionError):
            module.validate_finding_response({"results": [row]}, "A-01", 3)


def test_fallback_markers_are_strict():
    finding = {
        "results": [
            {"criterion_id": "A-01", "score": 2, "finding": module.UNAVAILABLE_FINDING}
        ]
    }
    assert module.validate_finding_response(finding, "A-01", 2, fallback=True)
    with pytest.raises(AgentExecutionError):
        module.validate_finding_response(finding, "A-01", 2)
    assert module.validate_summary_response(
        {"results": [{"summary": module.UNAVAILABLE_SUMMARY}]}, fallback=True
    )


@pytest.mark.parametrize(
    "text",
    [
        "The evidence supports a score of 2.",
        "A score 2 is appropriate.",
        "This receives 2/4.",
    ],
)
def test_prose_cannot_override_the_structured_score(text):
    with pytest.raises(AgentExecutionError, match="provided score"):
        module.validate_finding_response(
            {"results": [{"criterion_id": "OP-01", "score": 1, "finding": text}]},
            "OP-01",
            1,
        )


def test_summary_requires_trimmed_text_within_cap():
    assert (
        module.validate_summary_response({"results": [{"summary": "Summary."}]})
        == "Summary."
    )
    for text in ("", " padded ", "x" * 1201):
        with pytest.raises(AgentExecutionError):
            module.validate_summary_response({"results": [{"summary": text}]})
