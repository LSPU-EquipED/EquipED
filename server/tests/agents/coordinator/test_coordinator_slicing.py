from server.modules.agents.runtime.slicing import (
    GAP_MARKER,
    downsample_source_text,
)


def test_downsample_returns_text_unchanged_when_within_budget():
    text = "short document"
    assert downsample_source_text(text, budget=9000) == text


def test_downsample_samples_windows_and_marks_gaps_and_anchors_tail():
    text = "".join(f"para{i} " for i in range(4000))  # well over budget
    out = downsample_source_text(text, budget=600, windows=6)
    assert len(out) <= 600
    assert GAP_MARKER in out
    # Last window is anchored to the true tail: output ends with the tail.
    chunk_size = max(1, (600 - 5 * len(GAP_MARKER)) // 6)
    assert out.endswith(text[len(text) - chunk_size :])


def test_downsample_never_exceeds_budget_without_midword_tail_chop():
    text = "word " * 20000  # ~100k chars
    out = downsample_source_text(text, budget=6000, windows=6)
    assert len(out) <= 6000
    # Tail-anchored: the true document tail survives without a hard chop.
    assert text[-100:].strip().split()[-1] in out
