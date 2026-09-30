"""Tests for the house-rule correction script (adapter validation)."""

from __future__ import annotations

import uuid

import pytest
from server.modules.training_data.projectors import _is_score_shaped
from server.scripts import seed_house_rule_edits as tool


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1, (2, None)),
        (2, (3, None)),
        (3, (4, None)),
        (4, (None, "already_max")),
        (0, (None, "invalid_score")),
        (5, (None, "invalid_score")),
        (True, (None, "invalid_score")),
        ("3", (None, "invalid_score")),
        (None, (None, "invalid_score")),
        (3.0, (4, None)),
        (2.5, (None, "invalid_score")),
    ],
)
def test_apply_rule_raises_by_one_and_skips_the_ceiling(score, expected):
    assert tool.apply_rule(score) == expected


@pytest.mark.parametrize(
    "measurement",
    [
        {"criterion_id": "OP-01", "score": 2, "reasoning": "r"},
        {"criterion_id": "OP-01", "score": 2, "instances": []},
        {"criterion_id": "OP-01", "score": 2, "total_units": 3},
        {"criterion_id": "OP-01", "instances": []},
        {"criterion_id": "OP-01"},
    ],
)
def test_is_score_shaped_agrees_with_the_projector(measurement):
    assert tool.is_score_shaped(measurement) == _is_score_shaped(measurement)


@pytest.mark.parametrize(
    ("scores", "expected"),
    [([2, 3], 3), ([2, 2, 3], 2), ([3, 4], 4), ([1], 1), ([2, 2], 2)],
)
def test_base_reference_is_the_mean_rounded_half_up(scores, expected):
    assert tool.base_reference(scores) == expected


@pytest.mark.parametrize(
    ("role", "reference", "expected"),
    [("edited", 4, 4), ("edited", 2, 3), ("control", 2, 2), ("control", 4, 4)],
)
def test_expected_score_applies_the_rule_only_to_edited(role, reference, expected):
    assert tool.expected_score(role, reference) == expected


def test_normalize_codes_uppercases_dedupes_and_keeps_order():
    assert tool.normalize_codes([" op-01", "A-03 ", "", "OP-01"]) == ("OP-01", "A-03")


def test_default_edit_set_is_the_six_odd_numbered_criteria():
    assert tool.DEFAULT_EDIT_CRITERIA == (
        "OP-01",
        "OP-03",
        "OP-05",
        "A-01",
        "A-03",
        "A-05",
    )


def test_format_note_tags_the_run():
    run_id = uuid.uuid4()
    assert tool.format_note(run_id) == f"house-rule-seed:{run_id}"


def _criterion(code, *, role="edited", generation=None, new=None, skip=None):
    return tool.CriterionPlan(
        evaluation_id=uuid.UUID(int=1),
        generation_id=generation or uuid.UUID(int=2),
        criterion_code=code,
        role=role,
        base_score=2,
        new_score=new,
        skip_reason=skip,
    )


def _evaluation(group, criteria):
    return tool.EvaluationPlan(
        evaluation_id=uuid.UUID(int=1),
        document_id=uuid.UUID(int=3),
        document_title="Doc",
        group=group,
        generations=(),
        criteria=tuple(criteria),
    )


def test_only_train_plans_write_and_pair_generations_are_counted():
    gen_a, gen_b = uuid.UUID(int=10), uuid.UUID(int=11)
    train = _evaluation(
        "train",
        [
            _criterion("OP-01", generation=gen_a, new=3),
            _criterion("OP-03", generation=gen_a, new=4),
            _criterion("A-01", generation=gen_b, new=2),
            _criterion("A-03", generation=gen_b, skip="already_max"),
            _criterion("OP-02", role="control"),
        ],
    )
    reference = _evaluation("reference", [_criterion("OP-01", new=3)])
    run = tool.RunPlan(plans=(train, reference), edit_codes=("OP-01",))

    assert len(train.writes) == 3
    assert reference.writes == ()
    assert len(run.writes) == 3
    assert run.pair_generation_ids == frozenset({gen_a, gen_b})
    assert run.skip_counts() == {"already_max": 1}
