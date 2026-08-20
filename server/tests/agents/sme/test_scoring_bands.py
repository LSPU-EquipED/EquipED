"""Unit tests for the deterministic band functions."""

from __future__ import annotations

from server.modules.agents.sme.oracle.bands import count_band, mean_band, ratio_band


class TestRatioBand:
    def test_moderate_boundaries(self) -> None:
        assert ratio_band(80, 100).band == 4
        assert ratio_band(79, 100).band == 3
        assert ratio_band(50, 100).band == 3
        assert ratio_band(49, 100).band == 2
        assert ratio_band(20, 100).band == 2
        assert ratio_band(19, 100).band == 1

    def test_high_boundaries(self) -> None:
        assert ratio_band(90, 100, scale="high").band == 4
        assert ratio_band(89, 100, scale="high").band == 3
        assert ratio_band(70, 100, scale="high").band == 3
        assert ratio_band(40, 100, scale="high").band == 2
        assert ratio_band(39, 100, scale="high").band == 1

    def test_empty_denominator_scores_one(self) -> None:
        result = ratio_band(0, 0)
        assert result.band == 1
        assert result.pct is None

    def test_all_aligned(self) -> None:
        result = ratio_band(11, 11)
        assert result.band == 4
        assert result.pct == 100.0

    def test_spike_case_five_of_eleven(self) -> None:
        # The real A-05 spike: 5/11 = 45% -> moderate band 2.
        assert ratio_band(5, 11).band == 2


class TestCountBand:
    OP02 = ((5, 4), (3, 3), (1, 2))  # interaction types, of 7

    def test_count_thresholds(self) -> None:
        assert count_band(7, self.OP02) == 4
        assert count_band(5, self.OP02) == 4
        assert count_band(4, self.OP02) == 3
        assert count_band(3, self.OP02) == 3
        assert count_band(2, self.OP02) == 2
        assert count_band(1, self.OP02) == 2
        assert count_band(0, self.OP02) == 1


class TestMeanBand:
    def test_round_half_up(self) -> None:
        assert mean_band([4, 3]) == 4  # 3.5 -> 4
        assert mean_band([3, 2]) == 3  # 2.5 -> 3
        assert mean_band([2, 2, 1]) == 2  # 1.67 -> 2

    def test_empty_scores_one(self) -> None:
        assert mean_band([]) == 1

    def test_single_task(self) -> None:
        assert mean_band([3]) == 3
