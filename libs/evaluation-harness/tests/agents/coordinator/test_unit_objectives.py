"""Contracts for Coordinator v3 objective quotation grounding."""

import pytest
from equiped_harness.agents.coordinator.unit_objectives import (
    combine_objective_rows,
    objective_quote_catalog,
    validate_objective_rows,
)
from equiped_harness.exceptions import AgentExecutionError


def test_numbered_excerpts_ground_without_model_recopying():
    catalog = {
        "assessment-0001": {
            "source": "assessment",
            "text": "Compare the two habitats.\nExplain their different adaptations.",
        }
    }
    option = objective_quote_catalog(catalog)[0]
    rows = validate_objective_rows(
        [
            {
                "objective_id": "obj-02",
                "matches": [{"quote_id": option["quote_id"]}],
                "reason": "The comparison task assesses habitat differences.",
            }
        ],
        (OBJECTIVES[1],),
        catalog,
        "assessment",
    )
    assert rows[0]["matches"] == [
        {
            "source_id": "assessment-0001",
            "quote": catalog["assessment-0001"]["text"],
        }
    ]
    with pytest.raises(AgentExecutionError, match="quote_id"):
        validate_objective_rows(
            [
                {
                    "objective_id": "obj-02",
                    "matches": [{"quote_id": "unknown"}],
                    "reason": "An unsupported excerpt was selected.",
                }
            ],
            (OBJECTIVES[1],),
            catalog,
            "assessment",
        )


OBJECTIVES = (
    {"objective_id": "obj-01", "text": "Explain the water cycle"},
    {"objective_id": "obj-02", "text": "Compare local habitats"},
)
CATALOG = {
    "assessment-0001": {
        "source": "assessment",
        "text": "Students will describe\n evaporation and condensation in a diagram.",
    },
    "curriculum-0001": {
        "source": "curriculum",
        "text": "Learners compare two local habitats using evidence.",
    },
}


def test_validate_objectives_reconstructs_source_ids_and_retains_source_slice():
    rows = [
        {
            "objective_id": "obj-01",
            "matches": [
                {
                    "source_id": "assessment-0001",
                    "quote": "describe evaporation and condensation",
                }
            ],
            "reason": "The assessment requires learners to explain key stages.",
        },
        {
            "objective_id": "obj-02",
            "matches": [],
            "reason": "No matching curriculum activity was found.",
        },
    ]
    result = validate_objective_rows(rows, OBJECTIVES, CATALOG, "assessment")
    assert result[0]["matches"][0]["quote"] == "describe\n evaporation and condensation"
    assert result[0]["source_ids"] == ["assessment-0001"]
    assert result[1]["source_ids"] == []


@pytest.mark.parametrize(
    "rows, namespace",
    [
        (
            [
                {"objective_id": "obj-02", "matches": [], "reason": "gap"},
                {"objective_id": "obj-01", "matches": [], "reason": "gap"},
            ],
            "assessment",
        ),
        (
            [
                {
                    "objective_id": "obj-01",
                    "matches": [
                        {
                            "source_id": "curriculum-0001",
                            "quote": "compare two local habitats",
                        }
                    ],
                    "reason": "supported",
                },
                {"objective_id": "obj-02", "matches": [], "reason": "gap"},
            ],
            "assessment",
        ),
        (
            [
                {
                    "objective_id": "obj-01",
                    "matches": [
                        {
                            "source_id": "assessment-0001",
                            "quote": "Explain the water cycle",
                        }
                    ],
                    "reason": "supported",
                },
                {"objective_id": "obj-02", "matches": [], "reason": "gap"},
            ],
            "assessment",
        ),
    ],
)
def test_validation_rejects_order_namespace_and_self_quote(rows, namespace):
    with pytest.raises(AgentExecutionError):
        validate_objective_rows(rows, OBJECTIVES, CATALOG, namespace)


def test_persisted_source_ids_must_match_quote_sources():
    rows = [
        {
            "objective_id": "obj-01",
            "matches": [
                {"source_id": "assessment-0001", "quote": "describe evaporation"}
            ],
            "source_ids": [],
            "reason": "supported",
        },
        {"objective_id": "obj-02", "matches": [], "source_ids": [], "reason": "gap"},
    ]
    with pytest.raises(AgentExecutionError, match="source_ids"):
        validate_objective_rows(rows, OBJECTIVES, CATALOG, "assessment")


def test_combine_caps_matches_deduplicates_and_selects_supported_reasons():
    def rows(quote, reason):
        return [
            {
                "objective_id": "obj-01",
                "matches": [{"source_id": "assessment-0001", "quote": quote}],
                "reason": reason,
            },
            {
                "objective_id": "obj-02",
                "matches": [],
                "reason": "No relevant activity found.",
            },
        ]

    result = combine_objective_rows(
        [
            rows(
                "describe evaporation",
                "Assessment asks learners to explain evaporation.",
            ),
            rows("in a diagram", "Learners represent stages in a diagram."),
        ],
        OBJECTIVES,
        CATALOG,
        "assessment",
    )
    assert result[0]["source_ids"] == ["assessment-0001"]
    assert len(result[0]["matches"]) == 2
    assert "Assessment asks" in result[0]["reason"]
    assert result[1]["reason"] == "No relevant activity found."


def test_combine_accepts_ordered_packet_objective_subsets():
    objectives = tuple(
        {"objective_id": f"obj-{index:02d}", "text": f"Objective {index}"}
        for index in range(1, 10)
    )
    catalog = {
        "assessment-0001": {
            "source": "assessment",
            "text": "Students will practice each learning goal.",
        }
    }

    def make_row(objective):
        return {
            "objective_id": objective["objective_id"],
            "matches": [
                {"source_id": "assessment-0001", "quote": "practice each learning goal"}
            ],
            "reason": "Assessment includes a task for this goal.",
        }

    groups = [
        [make_row(objective) for objective in objectives[:8]],
        [make_row(objective) for objective in objectives[8:]],
    ]
    result = combine_objective_rows(groups, objectives, catalog, "assessment")
    assert [row["objective_id"] for row in result] == [
        objective["objective_id"] for objective in objectives
    ]
    assert all(row["matches"] for row in result)


def test_canonical_whitespace_quote_cannot_exceed_quote_limit():
    catalog = {
        "assessment-0001": {
            "source": "assessment",
            "text": "x" + (" " * 700) + "y",
        }
    }
    rows = [
        {
            "objective_id": "obj-01",
            "matches": [{"source_id": "assessment-0001", "quote": "x y"}],
            "reason": "This source supports the objective.",
        },
        {"objective_id": "obj-02", "matches": [], "reason": "No match found."},
    ]
    with pytest.raises(AgentExecutionError, match="Canonical objective quote"):
        validate_objective_rows(rows, OBJECTIVES, catalog, "assessment")


def test_identical_curriculum_outcome_can_establish_alignment():
    objective = {"objective_id": "OBJ-0001", "text": "Explain the water cycle."}
    catalog = {"curriculum-0001": {"source": "curriculum", "text": objective["text"]}}
    rows = validate_objective_rows(
        [
            {
                "objective_id": objective["objective_id"],
                "matches": [
                    {"source_id": "curriculum-0001", "quote": objective["text"]}
                ],
                "reason": "The curriculum explicitly includes the same outcome.",
            }
        ],
        (objective,),
        catalog,
        "curriculum",
    )
    assert rows[0]["source_ids"] == ["curriculum-0001"]
