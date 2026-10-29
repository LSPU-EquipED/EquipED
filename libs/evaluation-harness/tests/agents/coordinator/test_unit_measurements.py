from __future__ import annotations

import uuid

import pytest
from equiped_harness.agents.coordinator.catalog import CatalogItem
from equiped_harness.agents.coordinator.unit_measurements import (
    UNIT_POLICIES,
    combine_unit_rows,
    score_unit_row,
    validate_unit_row,
)
from equiped_harness.contracts import (
    CountBandConfig,
    CriterionDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
    ShortSampleConfig,
)
from equiped_harness.exceptions import AgentExecutionError

TEXT = (
    "Test one. Written response two. Reflection three. Performance task four. "
    "Project five. Oral assessment six. Self assessment seven."
)
CATALOG = {
    "slm-0001": CatalogItem("slm-0001", "slm", 0, len(TEXT), TEXT, "fingerprint")
}


def criterion(code: str, strategy):
    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=code,
        description="description",
        display_order=0,
        strategy_config=strategy,
    )


def item(
    quote: str, category: str, qualifies: bool = True, source_id: str = "slm-0001"
):
    return {
        "source_id": source_id,
        "quote": quote,
        "category": category,
        "qualifies": qualifies,
        "reason": "grounded",
    }


def count_config():
    return CountBandConfig(
        mode="minimum_count", threshold_4=5, threshold_3=3, threshold_2=1
    )


def ratio_config():
    return RatioBandConfig(
        mode="coverage_percentage", threshold_4=80, threshold_3=50, threshold_2=20
    )


def test_five_assessment_types_score_four_and_repeat_type_counts_once():
    c = criterion("A-02", count_config())
    row = {
        "status": "supported",
        "items": [
            item("Test one.", "objective_test"),
            item("Written response two.", "written_response"),
            item("Reflection three.", "reflection"),
            item("Performance task four.", "performance_task"),
            item("Project five.", "project"),
        ],
    }
    score, fact = score_unit_row(c, row, CATALOG)
    assert score.score == 4
    assert fact["count"] == 5
    duplicate_type = {
        "status": "supported",
        "items": row["items"] + [item("Oral assessment six.", "project")],
    }
    _, repeated_fact = score_unit_row(c, duplicate_type, CATALOG)
    assert repeated_fact["count"] == 5


def test_multiple_actual_interactive_tasks_in_same_parent_count_separately():
    c = criterion("OP-02", count_config())
    row = {
        "status": "supported",
        "items": [
            item("Test one.", "interactive_task"),
            item("Written response two.", "interactive_task"),
            item("Reflection three.", "interactive_task"),
            item("Performance task four.", "interactive_task"),
            item("Project five.", "interactive_task"),
        ],
    }
    assert score_unit_row(c, row, CATALOG)[1]["count"] == 5


def test_ratio_counts_all_real_tasks_and_qualifying_subset():
    c = criterion(
        "OP-01",
        RatioBandConfig(
            mode="coverage_percentage",
            threshold_4=80,
            threshold_3=60,
            threshold_2=40,
            short_sample=ShortSampleConfig(
                min_units=5, max_issues_4=0, max_issues_3=1, max_issues_2=2
            ),
        ),
    )
    row = {
        "status": "supported",
        "items": [
            item("Test one.", "topic_transition", True),
            item("Written response two.", "topic_transition", True),
            item("Reflection three.", "topic_transition", False),
        ],
    }
    _, fact = score_unit_row(c, row, CATALOG)
    assert (fact["total"], fact["qualifying"]) == (3, 2)


def test_exact_quote_and_category_are_required():
    c = criterion("OP-03", ratio_config())
    for bad in [
        item("fabricated", "student_task"),
        item("Test oner.", "student_task"),
        item("Test one.", "wrong"),
    ]:
        with pytest.raises(AgentExecutionError):
            validate_unit_row(c, {"status": "supported", "items": [bad]}, CATALOG)
    with pytest.raises(AgentExecutionError):
        validate_unit_row(
            c,
            {
                "status": "supported",
                "items": [item("Test one.", "student_task", source_id="elsewhere")],
            },
            CATALOG,
        )


def test_ambiguous_quote_is_rejected():
    text = "Task. Middle. Task."
    catalog = {"slm-0001": CatalogItem("slm-0001", "slm", 0, len(text), text, "x")}
    c = criterion("OP-03", ratio_config())
    with pytest.raises(AgentExecutionError, match="ambiguous"):
        validate_unit_row(
            c,
            {"status": "supported", "items": [item("Task.", "student_task")]},
            catalog,
        )


def test_merge_deduplicates_same_physical_occurrence_and_rejects_conflict():
    c = criterion("OP-03", ratio_config())
    row_a = {"status": "supported", "items": [item("Test one.", "student_task")]}
    row_b = {"status": "supported", "items": [item("Test one.", "student_task")]}
    merged = combine_unit_rows(c, [row_a, row_b], CATALOG)
    assert len(merged["items"]) == 1
    bad = {"status": "supported", "items": [item("Test one.", "student_task", False)]}
    with pytest.raises(AgentExecutionError, match="conflicting"):
        combine_unit_rows(c, [row_a, bad], CATALOG)


def test_persisted_canonical_fields_are_rederived_and_checked():
    c = criterion("OP-03", ratio_config())
    canonical = validate_unit_row(
        c,
        {"status": "supported", "items": [item("Test one.", "student_task")]},
        CATALOG,
    )
    canonical["items"][0]["start"] += 1
    with pytest.raises(AgentExecutionError):
        validate_unit_row(c, canonical, CATALOG)


def test_frozen_rubric_policies_match_active_strategy_families():
    ratio_codes = {"OP-01", "OP-03", "OP-04", "A-01"}
    for code in (
        "OP-01",
        "OP-02",
        "OP-03",
        "OP-04",
        "OP-05",
        "A-01",
        "A-02",
        "A-03",
        "A-04",
    ):
        config = (
            RatioBandConfig(
                mode="coverage_percentage",
                threshold_4=80,
                threshold_3=50,
                threshold_2=20,
            )
            if code in ratio_codes
            else count_config()
        )
        c = criterion(code, config)
        category = UNIT_POLICIES[code]["categories"][0]
        fact = score_unit_row(
            c, {"status": "supported", "items": [item("Test one.", category)]}, CATALOG
        )[1]
        assert fact["kind"] == ("ratio" if code in ratio_codes else "count")


def test_quote_is_scoped_to_packet_source_and_canonicalized_to_source_text():
    quote = "Test one."
    catalog = {
        "slm-a": CatalogItem("slm-a", "slm", 0, len(quote), quote, "a"),
        "slm-b": CatalogItem("slm-b", "slm", 100, 100 + len(quote), quote, "b"),
    }
    c = criterion("OP-02", count_config())
    row = {
        "status": "supported",
        "items": [item("  Test \n one. ", "interactive_task", source_id="slm-b")],
    }
    canonical = validate_unit_row(c, row, catalog)
    assert canonical["items"][0]["quote"] == quote
    assert canonical["items"][0]["start"] == 100


def test_maximum_count_mode_uses_existing_calculator():
    config = CountBandConfig(
        mode="maximum_count", threshold_4=0, threshold_3=2, threshold_2=4
    )
    c = criterion("OP-02", config)
    items = [item(q, "interactive_task") for q in TEXT.split(". ")[:5]]
    items = [dict(i, quote=i["quote"] + ".") for i in items]
    assert (
        score_unit_row(c, {"status": "supported", "items": items}, CATALOG)[0].score
        == 1
    )


def test_merged_limit_is_200_and_merged_row_can_be_scored():
    quotes = [f"Task occurrence {i}." for i in range(150)]
    source = " ".join(quotes)
    catalog = {"slm-0001": CatalogItem("slm-0001", "slm", 0, len(source), source, "x")}
    items = [item(quote, "interactive_task") for quote in quotes]
    c = criterion(
        "OP-02",
        CountBandConfig(
            mode="minimum_count", threshold_4=100, threshold_3=75, threshold_2=50
        ),
    )
    merged = combine_unit_rows(
        c,
        [
            {"status": "supported", "items": items[:75]},
            {"status": "supported", "items": items[75:]},
        ],
        catalog,
    )
    assert len(merged["items"]) == 150
    assert score_unit_row(c, merged, catalog)[1]["count"] == 150


def test_legacy_guidance_criteria_use_existing_ordinary_scorer():
    c = criterion("LEGACY", LlmRubricGuidanceConfig(guidance="Score the evidence."))
    score, fact = score_unit_row(
        c, {"status": "supported", "score": 3, "evidence_id": "slm-0001"}, CATALOG
    )
    assert score.score == 3
    assert fact["kind"] == "guidance"
