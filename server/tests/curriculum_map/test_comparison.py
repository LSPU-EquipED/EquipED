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
    "expected_level,weaker,stronger",
    [("D", "E", "D"), ("D", "I", "E"), ("E", "I", "D")],
)
def test_strictness_ordering_i_lt_e_lt_d(expected_level, weaker, stronger) -> None:
    # Sanity check the I < E < D ordering directly via compare_objective.
    assert (
        compare_objective(is_addressed=True, observed_level=weaker, expected_level=expected_level)
        != "over-developed"
    )
    assert (
        compare_objective(is_addressed=True, observed_level=stronger, expected_level=expected_level)
        != "under-developed"
    )
