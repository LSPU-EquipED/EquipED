"""Offline tests for training/smoke_test_lora_serving.py (no server, no GPU)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TRAINING_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_DIR))

import smoke_test_lora_serving as smoke  # noqa: E402


def _reply(*scores: int, summary: str = "ok") -> str:
    return json.dumps(
        {
            "summary": summary,
            "criterion_measurements": [
                {
                    "criterion_id": f"OP-0{index}",
                    "criterion_title": f"Title {index}",
                    "score": score,
                    "evidence": "quote",
                    "reasoning": "because",
                }
                for index, score in enumerate(scores, start=1)
            ],
        }
    )


_OK_ENTRY = {"criterion_id": "A", "score": 2}


def _measurements(*entries: dict) -> str:
    return json.dumps({"summary": "s", "criterion_measurements": list(entries)})


def test_valid_reply_returns_scores_and_ignores_extra_fields():
    result = smoke.validate_sme_reply(_reply(3, 4))
    assert result.valid is True
    assert result.reason is None
    assert result.scores == {"OP-01": 3, "OP-02": 4}


def test_code_fenced_reply_is_accepted():
    fenced = "```json\n" + _reply(2) + "\n```"
    result = smoke.validate_sme_reply(fenced)
    assert result.valid is True
    assert result.scores == {"OP-01": 2}


@pytest.mark.parametrize(
    ("text", "reason_fragment"),
    [
        ("", "empty"),
        ("   \n", "empty"),
        ("not json at all", "not valid JSON"),
        ("[1, 2, 3]", "not an object"),
        (json.dumps({"criterion_measurements": [_OK_ENTRY]}), "summary"),
        (json.dumps({"summary": "s"}), "criterion_measurements"),
        (_measurements(), "criterion_measurements"),
        (_measurements("x"), "not an object"),
        (_measurements({"score": 2}), "criterion_id"),
        (_measurements({"criterion_id": " ", "score": 2}), "criterion_id"),
        (_measurements({"criterion_id": "A", "score": True}), "integer"),
        (_measurements({"criterion_id": "A", "score": 2.5}), "integer"),
        (_measurements({"criterion_id": "A", "score": "3"}), "integer"),
        (_measurements({"criterion_id": "A"}), "integer"),
        (_measurements({"criterion_id": "A", "score": 0}), "out of range"),
        (_measurements({"criterion_id": "A", "score": 5}), "out of range"),
    ],
)
def test_invalid_replies_are_rejected_with_a_reason(text, reason_fragment):
    result = smoke.validate_sme_reply(text)
    assert result.valid is False
    assert reason_fragment in (result.reason or "")
    assert result.scores == {}


def test_load_prompts_reads_prompt_field_and_respects_limit(tmp_path):
    path = tmp_path / "pairs.jsonl"
    rows = [{"prompt": f"p{i}", "chosen": "c", "rejected": "r"} for i in range(4)]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n\n", encoding="utf-8")
    assert smoke.load_prompts(path, 2) == ["p0", "p1"]
    assert smoke.load_prompts(path, 10) == ["p0", "p1", "p2", "p3"]


def test_load_prompts_rejects_missing_prompt_and_bad_limit(tmp_path):
    path = tmp_path / "pairs.jsonl"
    path.write_text(json.dumps({"chosen": "c"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="prompt"):
        smoke.load_prompts(path, 1)
    with pytest.raises(ValueError, match="limit"):
        smoke.load_prompts(path, 0)


def test_load_prompts_rejects_empty_file(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no prompts"):
        smoke.load_prompts(path, 1)


def test_bundled_sample_pairs_hold_real_sme_prompts():
    prompts = smoke.load_prompts(TRAINING_DIR / "sample_pairs.jsonl", 10)
    assert len(prompts) == 2
    for prompt in prompts:
        assert "REQUIRED JSON OUTPUT STRUCTURE" in prompt
        assert "criterion_measurements" in prompt


def test_run_smoke_test_calls_off_then_on_and_compares_scores():
    calls: list[tuple[str, float]] = []

    def complete(prompt: str, scale: float) -> str:
        calls.append((prompt, scale))
        return _reply(2 if scale == 0.0 else 3)

    report = smoke.run_smoke_test(["p1", "p2"], complete)

    assert calls == [("p1", 0.0), ("p2", 0.0), ("p1", 1.0), ("p2", 1.0)]
    assert report.total == 2
    assert report.valid_off == 2
    assert report.valid_on == 2
    assert report.comparable == 2
    assert report.changed == 2
    assert report.all_valid is True
    assert smoke.exit_code(report) == 0


def test_run_smoke_test_reports_unchanged_scores():
    report = smoke.run_smoke_test(["p1"], lambda prompt, scale: _reply(2))
    assert report.comparable == 1
    assert report.changed == 0
    assert report.results[0].score_changed is False


def test_invalid_on_reply_fails_the_run_and_is_not_comparable():
    def complete(prompt: str, scale: float) -> str:
        return "garbage" if scale == 1.0 else _reply(2)

    report = smoke.run_smoke_test(["p1"], complete)

    assert report.valid_off == 1
    assert report.valid_on == 0
    assert report.comparable == 0
    assert report.results[0].score_changed is None
    assert report.all_valid is False
    assert smoke.exit_code(report) == 1


def test_scores_are_only_compared_on_shared_criteria():
    def complete(prompt: str, scale: float) -> str:
        criterion = "A" if scale == 0.0 else "B"
        return _measurements({"criterion_id": criterion, "score": 2})

    report = smoke.run_smoke_test(["p1"], complete)
    assert report.results[0].score_changed is False


def test_format_report_summarises_counts_and_lists_each_prompt():
    def complete(prompt: str, scale: float) -> str:
        if prompt == "bad" and scale == 1.0:
            return _measurements({"criterion_id": "OP-01", "score": 9})
        return _reply(2 if scale == 0.0 else 3)

    text = smoke.format_report(smoke.run_smoke_test(["good", "bad"], complete))

    assert "Adapter smoke test: 2 prompt(s)" in text
    assert "adapter OFF: 2/2 valid JSON" in text
    assert "adapter ON : 1/2 valid JSON" in text
    assert "score changed with adapter ON: 1/1 comparable prompt(s)" in text
    assert "RESULT: FAIL - 1 invalid reply(ies)" in text
    first = next(line for line in text.splitlines() if line.startswith("  #1"))
    assert "off=ok" in first and "on=ok" in first
    assert first.rstrip().endswith("scores changed")
    second = next(line for line in text.splitlines() if line.startswith("  #2"))
    assert "off=ok" in second and "on=INVALID" in second
    assert "on: measurement 0 score 9 out of range" in second


def test_format_report_passes_and_warns_when_no_score_changed():
    text = smoke.format_report(
        smoke.run_smoke_test(["p1"], lambda prompt, scale: _reply(2))
    )
    assert "RESULT: PASS - every reply was valid JSON" in text
    assert "NOTE: no score changed between OFF and ON" in text
    assert "--scale-mode global" in text


def test_format_report_has_no_note_when_scores_changed():
    text = smoke.format_report(
        smoke.run_smoke_test(["p1"], lambda prompt, scale: _reply(2 + int(scale)))
    )
    assert "NOTE:" not in text
