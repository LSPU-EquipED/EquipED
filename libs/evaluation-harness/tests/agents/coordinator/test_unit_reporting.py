from __future__ import annotations

import pytest
from equiped_harness.agents.coordinator.catalog import CatalogItem
from equiped_harness.agents.coordinator.unit_reporting import (
    build_objective_explanation,
    build_unit_explanation,
    build_unit_summary,
    render_unit_justification,
    validate_unit_explanation,
)

TEXT = "Learners compare evidence and justify decisions. A heading introduces a task."
CATALOG = {"slm-0001": CatalogItem("slm-0001", "slm", 0, len(TEXT), TEXT, "x")}


def test_unit_explanation_keeps_positive_and_negative_reasons_and_quotes():
    items = [
        {
            "item_id": "yes",
            "source_id": "slm-0001",
            "quote": "Learners compare evidence",
            "qualifies": True,
        },
        {
            "item_id": "no",
            "source_id": "slm-0001",
            "quote": "A heading introduces a task.",
            "qualifies": False,
        },
    ]
    decisions = [
        {
            "item_id": "yes",
            "source_id": "slm-0001",
            "decision": "qualifies",
            "reason": "The instruction asks learners to analyze evidence.",
        },
        {
            "item_id": "no",
            "source_id": "slm-0001",
            "decision": "does_not_qualify",
            "reason": "This is only a heading and gives no learner action.",
        },
    ]
    explanation, status = build_unit_explanation(
        criterion_title="Student tasks",
        fact={"kind": "count", "count": 1},
        packet_explanations=[],
        unavailable_packets=0,
        review_decisions=decisions,
        proposed_items=items,
    )
    assert status == "complete"
    assert "asks learners" in explanation["finding"]
    assert "only a heading" in explanation["finding"]
    assert [row["quote"] for row in explanation["evidence"]] == [
        item["quote"] for item in items
    ]


def test_positive_reason_does_not_erase_near_miss_rejection():
    items = [
        {
            "item_id": "yes",
            "source_id": "slm-0001",
            "quote": "Learners compare evidence",
            "qualifies": True,
        },
        {
            "item_id": "near",
            "source_id": "slm-0001",
            "quote": "A heading introduces a task.",
            "qualifies": False,
        },
    ]
    explanation, _ = build_unit_explanation(
        criterion_title="Tasks",
        fact={},
        packet_explanations=[],
        unavailable_packets=0,
        review_decisions=[
            {
                "item_id": "yes",
                "source_id": "slm-0001",
                "decision": "qualifies",
                "reason": "This asks learners to compare evidence.",
            },
            {
                "item_id": "near",
                "source_id": "slm-0001",
                "decision": "not_a_unit",
                "reason": "It is a heading rather than a learner task.",
            },
        ],
        proposed_items=items,
    )
    assert explanation["finding"].startswith("This asks")
    assert "rather than a learner task" in explanation["finding"]
    assert len(explanation["evidence"]) == 2


def test_partial_packet_limit_preserves_valid_finding_and_quote():
    item = {
        "item_id": "yes",
        "source_id": "slm-0001",
        "quote": "Learners compare evidence",
        "qualifies": True,
    }
    explanation, status = build_unit_explanation(
        criterion_title="Tasks",
        fact={},
        packet_explanations=[],
        unavailable_packets=2,
        review_decisions=[
            {
                "item_id": "yes",
                "source_id": "slm-0001",
                "decision": "qualifies",
                "reason": "Learners compare evidence to justify a decision.",
            }
        ],
        proposed_items=[item],
    )
    assert status == "partial"
    assert "compare evidence" in explanation["finding"]
    assert explanation["evidence"] == [
        {"source_id": "slm-0001", "quote": item["quote"]}
    ]
    assert (
        "Explanation unavailable for 2 evidence packet(s)" in explanation["limitation"]
    )
    assert "measured results remain valid" in explanation["limitation"]


def test_unavailable_explanation_preserves_valid_measurement_notice():
    explanation, status = build_unit_explanation(
        criterion_title="Tasks",
        fact={},
        packet_explanations=[],
        unavailable_packets=1,
        review_decisions=[],
        proposed_items=[],
    )
    assert status == "partial"
    assert explanation == {
        "finding": "Reasoning unavailable—review required.",
        "limitation": (
            "Explanation unavailable because some evidence packets could not be "
            "reviewed; measured results remain valid."
        ),
        "evidence": [],
    }


def test_unit_validation_uses_v3_caps_exact_quotes_and_whitespace_normalization():
    value = {
        "finding": "A useful two-sentence explanation. It keeps the complete reason.",
        "limitation": "",
        "evidence": [{"source_id": "slm-0001", "quote": "Learners compare   evidence"}],
    }
    normalized = validate_unit_explanation(value, CATALOG, {"slm-0001"})
    assert normalized["evidence"][0]["quote"] == "Learners compare evidence"
    with pytest.raises(ValueError, match="700 characters"):
        validate_unit_explanation(
            {**value, "evidence": [{"source_id": "slm-0001", "quote": "x" * 701}]},
            CATALOG,
            {"slm-0001"},
        )
    with pytest.raises(ValueError, match="finding"):
        validate_unit_explanation(
            {**value, "finding": "x" * 1201}, CATALOG, {"slm-0001"}
        )
    with pytest.raises(ValueError, match="limitation"):
        validate_unit_explanation(
            {**value, "limitation": "x" * 501}, CATALOG, {"slm-0001"}
        )


def test_objective_explanation_quotes_match_and_examples_unsupported_objective():
    result, status = build_objective_explanation(
        objectives=(
            {"objective_id": "obj-1", "text": "Compare evidence"},
            {"objective_id": "obj-2", "text": "Write a reflection"},
        ),
        rows=[
            {
                "objective_id": "obj-1",
                "source_ids": ["slm-0001"],
                "matches": [
                    {
                        "source_id": "slm-0001",
                        "quote": "Learners compare evidence",
                        "start": 0,
                        "end": 26,
                    }
                ],
                "reason": "A mapped task supports comparing evidence.",
            },
            {
                "objective_id": "obj-2",
                "source_ids": [],
                "matches": [],
                "reason": "No passage addresses writing a reflection.",
            },
        ],
        packet_explanations=[
            {"finding": "A task directly supports comparing evidence."}
        ],
        unavailable_packets=0,
        catalog=CATALOG,
    )
    assert status == "complete"
    assert "mapped task supports" in result["finding"]
    assert "writing a reflection" in result["finding"]
    assert "mapped task supports" in result["finding"]
    assert "No passage addresses" in result["finding"]
    assert result["evidence"] == [
        {"source_id": "slm-0001", "quote": "Learners compare evidence"}
    ]


def test_rendering_reports_count_and_ratio_units_and_summary_keeps_partial_status():
    explanation = {
        "finding": "Several concrete learner actions were identified.",
        "limitation": "",
        "evidence": [],
    }
    assert "4 assessment types" in render_unit_justification(
        explanation, {"kind": "count", "count": 4, "unit_label": "assessment_type"}, 3
    )
    assert "4 assessment types" in render_unit_justification(
        explanation, {"kind": "count", "count": 4, "unit_label": "assessment types"}, 3
    )
    assert "2 of 5 reviewed tasks" in render_unit_justification(
        explanation,
        {"kind": "ratio", "total": 5, "qualifying": 2, "unit_label": "task"},
        2,
    )
    assert "Guidance was identified" in render_unit_justification(
        explanation, {"kind": "guidance"}, 3
    )
    summary = build_unit_summary(
        [{"criterion_id": "A-02", "score": 3}, {"criterion_id": "A-03", "score": 1}],
        {"A-02": explanation, "A-03": {"finding": "Some progress records are absent."}},
        {"A-02": "complete", "A-03": "partial"},
    )
    assert (
        "A-02" in summary
        and "A-03" in summary
        and "explanation was unavailable" in summary
    )


def test_verifier_reasons_override_primary_prose_when_every_item_is_rejected():
    explanation, status = build_unit_explanation(
        criterion_title="Tasks",
        fact={"kind": "count", "count": 0},
        packet_explanations=[
            {"finding": "The material fully satisfies the criterion.", "evidence": []}
        ],
        unavailable_packets=0,
        review_decisions=[
            {
                "item_id": "heading",
                "decision": "not_a_unit",
                "reason": "This is a decorative heading only.",
            }
        ],
        proposed_items=[
            {
                "item_id": "heading",
                "source_id": "slm-0001",
                "quote": "A heading introduces a task.",
                "qualifies": False,
            }
        ],
    )
    assert status == "complete"
    assert "decorative heading" in explanation["finding"]
    assert "fully satisfies" not in explanation["finding"]


def test_short_sample_explanation_uses_issue_rule_instead_of_percentage():
    text = render_unit_justification(
        {"finding": "One transition was unclear.", "limitation": "", "evidence": []},
        {
            "kind": "ratio",
            "total": 1,
            "qualifying": 0,
            "unit_label": "topic transitions",
            "scoring_config": {"short_sample": {"min_units": 4}},
        },
        3,
    )
    assert "short-sample issue rule assigns 3/4" in text
    assert "1 of 1" in text
    assert "0.0%" not in text
