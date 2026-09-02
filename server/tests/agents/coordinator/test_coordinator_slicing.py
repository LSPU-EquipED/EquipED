from server.modules.agents.coordinator.slicing import GAP_MARKER, downsample


def test_downsample_returns_text_unchanged_when_within_budget():
    text = "short document"
    assert downsample(text, budget=9000) == text


def test_downsample_samples_windows_and_marks_gaps_and_anchors_tail():
    text = "".join(f"para{i} " for i in range(4000))  # well over budget
    out = downsample(text, budget=600, windows=6)
    assert len(out) <= 600 + 5 * len(GAP_MARKER)
    assert GAP_MARKER in out
    assert out.endswith(text[-100:][-(600 // 6):])
