"""Unit tests for the pure I/E/D comparison logic.

No LLM, no IO -- exercises every branch of the priority-ordered status
rule from the design spec (docs/superpowers/specs/2026-07-30-curriculum-
alignment-pipeline-design.md section 5): is_addressed is checked first and
overrides whatever observed_level accompanies it.
"""

from __future__ import annotations

import pytest
from server.modules.curriculum_map.comparison import compare_objective


def test_not_addressed_when_is_addressed_false() -> None:
    assert (
        compare_objective(is_addressed=False, observed_level=None, expected_level="D")
        == "not_addressed"
    )


def test_not_addressed_overrides_a_stray_observed_level() -> None:
    # is_addressed takes priority even if observed_level is non-null.
    assert (
        compare_objective(is_addressed=False, observed_level="D", expected_level="D")
        == "not_addressed"
    )


def test_match_when_levels_equal() -> None:
    assert (
        compare_objective(is_addressed=True, observed_level="E", expected_level="E")
        == "match"
    )


def test_under_developed_when_observed_shallower() -> None:
    assert (
        compare_objective(is_addressed=True, observed_level="I", expected_level="D")
        == "under-developed"
    )


def test_over_developed_when_observed_deeper() -> None:
    assert (
        compare_objective(is_addressed=True, observed_level="D", expected_level="I")
        == "over-developed"
    )


@pytest.mark.parametrize(
    "expected_level,weaker",
    [("E", "I"), ("D", "I"), ("D", "E")],
)
def test_weaker_observed_level_never_over_developed(expected_level, weaker) -> None:
    # A strictly weaker observed_level must never read as over-developed.
    # D and I have no valid "weaker" partner outside these pairs (I is the
    # floor, so it never appears as `expected_level` here).
    result = compare_objective(
        is_addressed=True, observed_level=weaker, expected_level=expected_level
    )
    assert result != "over-developed"


@pytest.mark.parametrize(
    "expected_level,stronger",
    [("I", "E"), ("I", "D"), ("E", "D")],
)
def test_stronger_observed_level_never_under_developed(
    expected_level, stronger
) -> None:
    # A strictly stronger observed_level must never read as under-developed.
    # D has no valid "stronger" partner (it's the ceiling), so it never
    # appears as `expected_level` here.
    result = compare_objective(
        is_addressed=True, observed_level=stronger, expected_level=expected_level
    )
    assert result != "under-developed"
