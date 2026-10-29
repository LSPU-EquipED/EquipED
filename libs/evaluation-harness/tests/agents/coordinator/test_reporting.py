"""Tests for bounded source-grounded Coordinator explanations."""

from __future__ import annotations

import pytest
from equiped_harness.agents.coordinator.catalog import CatalogItem
from equiped_harness.agents.coordinator.reporting import (
    evidence_quotes,
    render_justification,
    selected_source_ids,
    unavailable_explanation,
    validate_explanation,
)


@pytest.fixture
def catalog():
    return {
        "slm-0001": CatalogItem(
            "slm-0001",
            "slm",
            0,
            38,
            "Learners compare evidence and justify decisions.",
            "x",
        ),
        "curriculum-0001": CatalogItem(
            "curriculum-0001", "curriculum", 0, 22, "Compare evidence fairly.", "y"
        ),
    }


def test_explanation_requires_literal_substring_from_selected_source(catalog):
    valid = {
        "finding": "The unit asks learners to compare evidence.",
        "limitation": "",
        "evidence": [{"source_id": "slm-0001", "quote": "compare evidence"}],
    }
    assert validate_explanation(valid, catalog, {"slm-0001"}) == valid
    with pytest.raises(ValueError, match="exact source substring"):
        validate_explanation(
            {
                **valid,
                "evidence": [
                    {"source_id": "slm-0001", "quote": "compare evidence fairly"}
                ],
            },
            catalog,
            {"slm-0001"},
        )


def test_explanation_rejects_unselected_sources_duplicates_and_oversize(catalog):
    item = {"source_id": "slm-0001", "quote": "compare evidence"}
    base = {"finding": "Supported.", "limitation": "", "evidence": [item]}
    with pytest.raises(ValueError, match="selected in results"):
        validate_explanation(
            {
                **base,
                "evidence": [
                    {"source_id": "curriculum-0001", "quote": "Compare evidence"}
                ],
            },
            catalog,
            {"slm-0001"},
        )
    with pytest.raises(ValueError, match="duplicate"):
        validate_explanation({**base, "evidence": [item, item]}, catalog, {"slm-0001"})
    with pytest.raises(ValueError, match="finding"):
        validate_explanation({**base, "finding": "x" * 401}, catalog, {"slm-0001"})


def test_whole_quote_matches_pdf_line_wraps_and_retains_source_bytes():
    catalog = {
        "slm-0001": CatalogItem(
            "slm-0001", "slm", 0, 33, "Learners compare\nevidence fairly.", "x"
        )
    }
    value = {
        "finding": "Learners are asked to compare evidence.",
        "limitation": "",
        "evidence": [{"source_id": "slm-0001", "quote": "compare evidence fairly."}],
    }
    normalized = validate_explanation(value, catalog, {"slm-0001"})
    assert normalized["evidence"][0]["quote"] == "compare\nevidence fairly."
    with pytest.raises(ValueError, match="exact source substring"):
        validate_explanation(
            {
                **value,
                "evidence": [
                    {"source_id": "slm-0001", "quote": "compare false evidence fairly."}
                ],
            },
            catalog,
            {"slm-0001"},
        )


def test_missing_measurement_requires_limitation_and_no_quotes(catalog):
    valid = {
        "finding": "No assessment was available.",
        "limitation": "No assessment text was supplied.",
        "evidence": [],
    }
    assert validate_explanation(valid, catalog, set()) == valid
    with pytest.raises(ValueError, match="requires a limitation"):
        validate_explanation({**valid, "limitation": ""}, catalog, set())


def test_selected_sources_and_deterministic_rendering():
    fact = {"rows": [{"source_ids": ["assessment-0001"]}, {"source_ids": []}]}
    assert selected_source_ids(fact, kind="objective") == {"assessment-0001"}
    assert selected_source_ids({"instance_ids": ["a", "b"]}, kind="count") == {"a", "b"}
    explanation = {
        "finding": "Four objectives have support.",
        "limitation": "",
        "evidence": [],
    }
    rendered = render_justification(explanation, fact, 3, kind="objective")
    assert rendered == (
        "Four objectives have support. Assessment tasks support 1 of 2 learning "
        "objectives (50.0%), giving 3/4."
    )
    assert evidence_quotes({"evidence": [{"quote": "one"}, {"quote": "two"}]}) == (
        "one",
        "two",
    )


def test_unavailable_explanation_is_fixed_and_uses_no_model_text():
    assert unavailable_explanation() == {
        "finding": "Reasoning unavailable—review required.",
        "limitation": (
            "Measurements passed validation, but the model explanation could not "
            "be verified after repair."
        ),
        "evidence": [],
    }
