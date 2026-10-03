"""apps/server/tests/training_data/test_training_summary.py"""

from __future__ import annotations

import logging

import pytest
from server.modules.training_data.training_summary import (
    TrainingSummary,
    extract_training_summary,
)

FULL = {
    "version": 1,
    "steps": 12,
    "epochs": 3.0,
    "first": {
        "step": 1,
        "loss": 0.69,
        "margin": 0.0,
        "accuracy": 0.5,
        "chosen": 0.0,
        "rejected": 0.0,
    },
    "last": {
        "step": 12,
        "loss": 0.21,
        "margin": 1.4,
        "accuracy": 1.0,
        "chosen": 0.3,
        "rejected": -1.1,
    },
    "heldout": {"pair_count": 7, "loss": 0.4, "margin": 0.9, "accuracy": 0.86},
}


def test_full_summary_round_trips():
    assert extract_training_summary(FULL) == FULL


def test_partial_summary_keeps_only_present_values():
    result = extract_training_summary({"version": 1, "last": {"margin": 1.4}})
    assert result == {"version": 1, "last": {"margin": 1.4}}


def test_integers_are_accepted_as_metric_values():
    result = extract_training_summary({"last": {"margin": 1, "accuracy": 1}})
    assert result == {"version": 1, "last": {"margin": 1.0, "accuracy": 1.0}}


@pytest.mark.parametrize("raw", [None, {}, {"version": 1}, [], "text", 5, True])
def test_nothing_useful_returns_none(raw):
    assert extract_training_summary(raw) is None


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), float("-inf"), True, "1.4", 1e12, -1e12],
)
def test_invalid_metric_value_makes_the_summary_none(bad_value):
    raw = {"version": 1, "last": {"margin": bad_value}}
    assert extract_training_summary(raw) is None


def test_explicit_null_counts_as_missing():
    assert extract_training_summary({"version": 1, "last": {"margin": None}}) is None


def test_empty_nested_objects_are_not_a_summary():
    assert extract_training_summary({"version": 1, "last": {}}) is None


def test_unknown_keys_are_dropped():
    raw = {"version": 1, "junk": 1, "last": {"margin": 1.4, "extra": "x"}}
    assert extract_training_summary(raw) == {"version": 1, "last": {"margin": 1.4}}


def test_unknown_version_is_ignored():
    assert extract_training_summary({"version": 2, "last": {"margin": 1.0}}) is None


def test_negative_or_fractional_counts_are_invalid():
    assert extract_training_summary({"steps": -1, "last": {"margin": 1.0}}) is None
    assert extract_training_summary({"steps": 1.5, "last": {"margin": 1.0}}) is None


def test_invalid_summary_logs_a_warning(caplog):
    with caplog.at_level(logging.WARNING):
        extract_training_summary({"last": {"margin": float("nan")}})
    assert "training_summary" in caplog.text


def test_model_is_usable_for_api_responses():
    parsed = TrainingSummary.model_validate(FULL)
    assert parsed.last is not None and parsed.last.margin == 1.4
