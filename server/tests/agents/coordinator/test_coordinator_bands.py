from server.modules.agents.coordinator.bands import count_band, ratio_band


def test_ratio_band_moderate_thresholds():
    assert ratio_band(8, 10).band == 4
    assert ratio_band(5, 10).band == 3
    assert ratio_band(2, 10).band == 2
    assert ratio_band(1, 10).band == 1


def test_ratio_band_empty_denominator_scores_one():
    r = ratio_band(0, 0)
    assert r.band == 1
    assert r.pct is None


def test_count_band():
    thresholds = ((5, 4), (3, 3), (2, 2))
    assert count_band(6, thresholds) == 4
    assert count_band(3, thresholds) == 3
    assert count_band(1, thresholds) == 1
