"""Deterministic band functions: measurements -> 1-4 score.

Pure, side-effect free, and unit-tested. These encode the scoring bands
so that scoring is consistent by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

# Percentage band scales: (min_pct_inclusive, band), highest first.
MODERATE: tuple[tuple[float, int], ...] = ((80.0, 4), (50.0, 3), (20.0, 2))
HIGH: tuple[tuple[float, int], ...] = ((90.0, 4), (70.0, 3), (40.0, 2))
_SCALES = {"moderate": MODERATE, "high": HIGH}


@dataclass(frozen=True)
class RatioBand:
    """Result of a coverage-ratio scoring (e.g. aligned objectives / total)."""

    numerator: int
    denominator: int
    pct: float | None  # None when there was nothing to measure
    band: int


def ratio_band(
    numerator: int,
    denominator: int,
    *,
    scale: str = "moderate",
    empty_score: int = 1,
) -> RatioBand:
    """Score a coverage ratio against a percentage scale.

    An empty denominator means there were no units to measure; per the design,
    that absence is a real deficiency and scores ``empty_score`` (default 1).
    """
    thresholds = _SCALES[scale]
    if denominator <= 0:
        return RatioBand(numerator, denominator, None, empty_score)

    pct = numerator / denominator * 100.0
    band = 1
    for min_pct, candidate in thresholds:
        if pct >= min_pct:
            band = candidate
            break
    return RatioBand(numerator, denominator, pct, band)


def count_band(count: int, thresholds: tuple[tuple[int, int], ...]) -> int:
    """Score a distinct/checklist count against count thresholds.

    ``thresholds`` is ``((min_count, band), ...)`` highest first; anything below
    the lowest threshold scores 1. Example for OP-02 (of 7 interaction types):
    ``((5, 4), (3, 3), (1, 2))``.
    """
    for min_count, band in thresholds:
        if count >= min_count:
            return band
    return 1


def mean_band(scores: list[int]) -> int:
    """Average per-unit scores and round half-up to a 1-4 band.

    Empty (no units scored) -> 1, consistent with the empty-denominator rule.
    """
    if not scores:
        return 1
    mean = sum(scores) / len(scores)
    return int(mean + 0.5)  # round half-up; scores are positive


__all__ = ["RatioBand", "ratio_band", "count_band", "mean_band"]
