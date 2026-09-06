"""Tests for the Coordinator envelope response schema, parser, and grounding."""

from __future__ import annotations

import json
import uuid

import pytest
from server.modules.agents.coordinator.response import (
    COORD_TEXT_MAX,
    parse_and_validate_envelope_response,
)
from server.modules.agents.exceptions import AgentExecutionError
from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    RatioBandConfig,
)

SOURCE = "Objective: explain photosynthesis. Objective: describe cell walls."
CURRICULUM = "Unit 2 covers photosynthesis and light reactions in detail."


def make_criterion(code: str, *, strategy: str) -> CriterionDefinition:
    """Local builder standing in for the absent shared test helper."""
    if strategy == "curriculum_alignment":
        config = CurriculumAlignmentConfig()
    elif strategy == "count_band":
        config = CountBandConfig(
            mode="minimum_count", threshold_4=4, threshold_3=2, threshold_2=1
        )
    elif strategy == "ratio_band":
        config = RatioBandConfig(
            mode="coverage_percentage", threshold_4=90, threshold_3=75, threshold_2=60
        )
    else:  # pragma: no cover - guard for typos
        raise ValueError(f"unknown strategy {strategy!r}")

    return CriterionDefinition(
        rubric_criterion_id=uuid.uuid4(),
        criterion_code=code,
        title=f"{code} title",
        description=f"{code} description",
        display_order=0,
        strategy_config=config,
    )


def _wrap(measurements):
    return json.dumps({"summary": "ok", "criterion_measurements": measurements})


def test_curriculum_alignment_grounded_row_kept():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    raw = _wrap(
        [
            {
                "criterion_id": "A-05",
                "criterion_title": crit.title,
                "alignments": [
                    {
                        "objective_text": "Objective: explain photosynthesis.",
                        "is_aligned": True,
                        "assessment_excerpt": (
                            "Unit 2 covers photosynthesis and light reactions"
                        ),
                        "reasoning": "direct topic match",
                    }
                ],
            }
        ]
    )
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    m = out["criterion_measurements"][0]
    assert m["alignments"][0]["is_aligned"] is True
    assert m["_grounding_rejected_count"] == 0


def test_curriculum_alignment_ungrounded_row_demoted():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    raw = _wrap(
        [
            {
                "criterion_id": "A-05",
                "criterion_title": crit.title,
                "alignments": [
                    {
                        "objective_text": "Objective: describe cell walls.",
                        "is_aligned": True,
                        "assessment_excerpt": (
                            "Curriculum discusses mitochondria at length"
                        ),
                        "reasoning": "made up",
                    }
                ],
            }
        ]
    )
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    m = out["criterion_measurements"][0]
    assert m["alignments"][0]["is_aligned"] is False
    assert m["alignments"][0]["assessment_excerpt"] is None
    assert m["_grounding_rejected_count"] == 1


def test_objective_text_not_in_source_rejected():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    raw = _wrap(
        [
            {
                "criterion_id": "A-05",
                "criterion_title": crit.title,
                "alignments": [
                    {
                        "objective_text": "Objective: fabricate quantum tunneling.",
                        "is_aligned": False,
                        "assessment_excerpt": None,
                    }
                ],
            }
        ]
    )
    with pytest.raises(AgentExecutionError):
        parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)


def test_duplicate_objective_text_rejected():
    crit = make_criterion("A-05", strategy="curriculum_alignment")
    raw = _wrap(
        [
            {
                "criterion_id": "A-05",
                "criterion_title": crit.title,
                "alignments": [
                    {
                        "objective_text": "Objective: explain photosynthesis.",
                        "is_aligned": False,
                        "assessment_excerpt": None,
                    },
                    {
                        "objective_text": "Objective: explain photosynthesis.",
                        "is_aligned": False,
                        "assessment_excerpt": None,
                    },
                ],
            }
        ]
    )
    with pytest.raises(AgentExecutionError, match="duplicate objective_text"):
        parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)


def test_non_curriculum_criteria_still_validated_like_sme():
    crit = make_criterion("OP-02", strategy="count_band")
    raw = _wrap(
        [
            {
                "criterion_id": "OP-02",
                "criterion_title": crit.title,
                "instances": [{"excerpt": "Objective: explain photosynthesis."}],
            }
        ]
    )
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    assert out["criterion_measurements"][0]["instances"][0]["excerpt"] in SOURCE


def test_ratio_evidence_whitespace_is_canonicalized_to_exact_source_span():
    crit = make_criterion("OP-01", strategy="ratio_band")
    source = "Unit 1:\nLearning objectives are clearly stated."
    raw = _wrap(
        [
            {
                "criterion_id": "OP-01",
                "criterion_title": crit.title,
                "total_units": [
                    {
                        "evidence": "Unit 1: Learning objectives are clearly stated.",
                        "qualifies": True,
                    }
                ],
                "has_measurable_content": True,
            }
        ]
    )

    out = parse_and_validate_envelope_response(raw, (crit,), source, CURRICULUM)

    m = out["criterion_measurements"][0]
    assert m["total_units"][0]["evidence"] == source
    assert m["total_units"][0]["unit_id"] == "u1"
    assert "qualifies" not in m["total_units"][0]
    assert m["qualifying_unit_ids"] == ["u1"]


@pytest.mark.parametrize(
    "evidence",
    [
        "A fabricated objective.",
        "Objective: explain mitosis.",
        "Objective: describe mitochondria in depth.",
    ],
)
def test_ratio_evidence_not_present_in_source_remains_rejected(evidence):
    crit = make_criterion("OP-01", strategy="ratio_band")
    raw = _wrap(
        [
            {
                "criterion_id": "OP-01",
                "criterion_title": crit.title,
                "total_units": [{"evidence": evidence, "qualifies": True}],
                "has_measurable_content": True,
            }
        ]
    )

    with pytest.raises(AgentExecutionError, match=r"unit\[0\] evidence"):
        parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)


@pytest.mark.parametrize(
    "evidence",
    [
        "objective: explain photosynthesis.",
        "Objective - explain photosynthesis.",
        "Objective:\u00a0explain photosynthesis.",
    ],
)
def test_ratio_evidence_tolerant_variants_canonicalize(evidence):
    """Tolerant grounding accepts case, dash, and nbsp variants as the source span."""
    crit = make_criterion("OP-01", strategy="ratio_band")
    raw = _wrap(
        [
            {
                "criterion_id": "OP-01",
                "criterion_title": crit.title,
                "total_units": [{"evidence": evidence, "qualifies": True}],
                "has_measurable_content": True,
            }
        ]
    )
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    m = out["criterion_measurements"][0]
    assert m["total_units"][0]["evidence"] == "Objective: explain photosynthesis."
    assert m["qualifying_unit_ids"] == ["u1"]


def test_ratio_qualifies_flags_canonicalize_to_u1_u2_with_derived_ids():
    crit = make_criterion("OP-01", strategy="ratio_band")
    raw = _wrap(
        [
            {
                "criterion_id": "OP-01",
                "criterion_title": crit.title,
                "total_units": [
                    {
                        "evidence": "Objective: explain photosynthesis.",
                        "qualifies": True,
                    },
                    {
                        "evidence": "Objective: describe cell walls.",
                        "qualifies": False,
                    },
                ],
                "has_measurable_content": True,
            }
        ]
    )

    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)

    m = out["criterion_measurements"][0]
    assert [u["unit_id"] for u in m["total_units"]] == ["u1", "u2"]
    assert all("qualifies" not in u for u in m["total_units"])
    assert m["qualifying_unit_ids"] == ["u1"]


def test_ratio_old_linkage_keys_are_rejected():
    crit = make_criterion("OP-01", strategy="ratio_band")
    with_model_ids = _wrap(
        [
            {
                "criterion_id": "OP-01",
                "criterion_title": crit.title,
                "total_units": [
                    {
                        "unit_id": "u1",
                        "evidence": "Objective: explain photosynthesis.",
                        "qualifies": True,
                    }
                ],
                "has_measurable_content": True,
            }
        ]
    )
    with pytest.raises(AgentExecutionError, match="unexpected keys"):
        parse_and_validate_envelope_response(
            with_model_ids, (crit,), SOURCE, CURRICULUM
        )

    with_linkage_ids = _wrap(
        [
            {
                "criterion_id": "OP-01",
                "criterion_title": crit.title,
                "total_units": [
                    {
                        "evidence": "Objective: explain photosynthesis.",
                        "qualifies": True,
                    }
                ],
                "qualifying_unit_ids": ["u1"],
                "has_measurable_content": True,
            }
        ]
    )
    with pytest.raises(AgentExecutionError, match="unexpected keys"):
        parse_and_validate_envelope_response(
            with_linkage_ids, (crit,), SOURCE, CURRICULUM
        )


def test_count_same_excerpt_different_annotations_dedupes_keep_first():
    """Location/label annotations cannot bypass dedupe; same excerpt keep-first."""
    crit = make_criterion("OP-02", strategy="count_band")
    raw = _wrap(
        [
            {
                "criterion_id": "OP-02",
                "criterion_title": crit.title,
                "instances": [
                    {
                        "excerpt": "Objective: explain photosynthesis.",
                        "explanation": "first explanation",
                        "location": "p. 1",
                    },
                    {
                        "excerpt": "Objective:  explain   photosynthesis.",
                        "explanation": "second explanation",
                        "location": "p. 2",
                    },
                ],
            }
        ]
    )
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    m = out["criterion_measurements"][0]
    assert len(m["instances"]) == 1
    assert m["instances"][0]["excerpt"] == "Objective: explain photosynthesis."
    assert m["instances"][0]["explanation"] == "first explanation"
    assert m["instances"][0]["location"] == "p. 1"


def test_ratio_same_evidence_different_annotations_dedupes_contiguous():
    """Same evidence dedupes regardless of location/label; IDs stay u1..uN."""
    crit = make_criterion("OP-01", strategy="ratio_band")
    raw = _wrap(
        [
            {
                "criterion_id": "OP-01",
                "criterion_title": crit.title,
                "total_units": [
                    {
                        "evidence": "Objective: explain photosynthesis.",
                        "qualifies": True,
                        "label": "Alpha",
                        "location": "p. 1",
                    },
                    {
                        "evidence": "Objective: describe cell walls.",
                        "qualifies": False,
                    },
                    {
                        "evidence": "Objective:  explain   photosynthesis.",
                        "qualifies": True,
                        "label": "Beta",
                        "location": "p. 2",
                    },
                ],
                "has_measurable_content": True,
            }
        ]
    )
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    m = out["criterion_measurements"][0]
    assert [u["unit_id"] for u in m["total_units"]] == ["u1", "u2"]
    assert len(m["total_units"]) == 2
    assert m["total_units"][0]["evidence"] == "Objective: explain photosynthesis."
    assert m["total_units"][0]["label"] == "Alpha"
    assert m["total_units"][0]["location"] == "p. 1"
    assert all("qualifies" not in u for u in m["total_units"])
    assert m["qualifying_unit_ids"] == ["u1"]


def test_ratio_different_evidence_same_annotations_remains_distinct():
    """Different grounded evidence stays distinct even with same label/location."""
    crit = make_criterion("OP-01", strategy="ratio_band")
    raw = _wrap(
        [
            {
                "criterion_id": "OP-01",
                "criterion_title": crit.title,
                "total_units": [
                    {
                        "evidence": "Objective: explain photosynthesis.",
                        "qualifies": True,
                        "label": "Same Label",
                        "location": "p. 1",
                    },
                    {
                        "evidence": "Objective: describe cell walls.",
                        "qualifies": True,
                        "label": "Same Label",
                        "location": "p. 1",
                    },
                ],
                "has_measurable_content": True,
            }
        ]
    )
    out = parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)
    m = out["criterion_measurements"][0]
    assert [u["unit_id"] for u in m["total_units"]] == ["u1", "u2"]
    assert len(m["total_units"]) == 2
    assert m["qualifying_unit_ids"] == ["u1", "u2"]


def test_ratio_duplicate_conflicting_qualifies_raises():
    """Same evidence opposite qualifies conflicts despite differing annotations."""
    crit = make_criterion("OP-01", strategy="ratio_band")
    raw = _wrap(
        [
            {
                "criterion_id": "OP-01",
                "criterion_title": crit.title,
                "total_units": [
                    {
                        "evidence": "Objective: explain photosynthesis.",
                        "qualifies": True,
                        "label": "Alpha",
                        "location": "p. 1",
                    },
                    {
                        "evidence": "Objective:  explain   photosynthesis.",
                        "qualifies": False,
                        "label": "Beta",
                        "location": "p. 2",
                    },
                ],
                "has_measurable_content": True,
            }
        ]
    )
    with pytest.raises(AgentExecutionError, match="conflicting qualifies"):
        parse_and_validate_envelope_response(raw, (crit,), SOURCE, CURRICULUM)


def test_count_bounded_canonical_span_rejected_not_stored():
    """Whitespace-expanded match spanning >COORD_TEXT_MAX must stay rejected."""
    crit = make_criterion("OP-02", strategy="count_band")
    source = "hello" + " " * (COORD_TEXT_MAX + 500) + "world"
    assert len(source) > COORD_TEXT_MAX
    raw = _wrap(
        [
            {
                "criterion_id": "OP-02",
                "criterion_title": crit.title,
                "instances": [{"excerpt": "hello world"}],
            }
        ]
    )
    with pytest.raises(AgentExecutionError, match="excerpt is not"):
        parse_and_validate_envelope_response(raw, (crit,), source, CURRICULUM)
