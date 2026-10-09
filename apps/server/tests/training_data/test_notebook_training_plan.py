"""Tests for the planning helpers inside the training notebook (no GPU, no unsloth)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
NOTEBOOK_PATH = REPO_ROOT / "docs" / "colab" / "dpo_training_template.ipynb"
START = "# --- planning helpers (tested) ---"
END = "# --- end planning helpers ---"


def _cell(index: int) -> str:
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return "".join(nb["cells"][index]["source"])


def _helpers(index: int) -> dict:
    source = _cell(index)
    assert START in source and END in source
    block = source[source.index(START) : source.index(END)]
    namespace: dict = {"math": __import__("math")}
    exec(block, namespace)  # noqa: S102
    return namespace


def _count(text: str) -> int:
    return len(text.split())  # one "token" per word keeps the numbers readable


def _row(prompt_words: int, chosen_words: int = 10, rejected_words: int = 10) -> dict:
    return {
        "prompt": " ".join(["p"] * prompt_words),
        "chosen": " ".join(["c"] * chosen_words),
        "rejected": " ".join(["r"] * rejected_words),
    }


# ---- Task 1: length plan -------------------------------------------------


def test_lengths_are_rounded_up_with_a_margin():
    plan = _helpers(6)["plan_lengths"]([_row(100), _row(130, 20, 30)], _count, 6144)
    assert plan["keep"] == [0, 1] and plan["dropped"] == []
    assert plan["max_prompt_length"] == 192  # 130 rounded up to a multiple of 64
    # longest pair = 130 + 30 = 160, plus a 64 margin = 224, rounded up to 256
    assert plan["max_seq_length"] == 256
    assert plan["stats"]["pairs"] == 2 and plan["stats"]["prompt_max"] == 130


def test_pairs_over_the_ceiling_are_dropped_and_reported():
    rows = [_row(100)] + [_row(7000)] * 1 + [_row(120)] * 8
    plan = _helpers(6)["plan_lengths"](rows, _count, 6144)
    assert plan["dropped"] == [1]
    assert 1 not in plan["keep"] and len(plan["keep"]) == 9
    assert plan["max_seq_length"] <= 6144


def test_too_many_dropped_pairs_stop_the_run():
    rows = [_row(100)] * 7 + [_row(7000)] * 3  # 30% over the ceiling
    with pytest.raises(ValueError, match="ceiling"):
        _helpers(6)["plan_lengths"](rows, _count, 6144)


def test_exactly_the_allowed_fraction_is_accepted():
    rows = [_row(100)] * 8 + [_row(7000)] * 2  # exactly 20%
    plan = _helpers(6)["plan_lengths"](rows, _count, 6144)
    assert plan["dropped"] == [8, 9]


def test_everything_over_the_ceiling_is_an_error():
    with pytest.raises(ValueError):
        _helpers(6)["plan_lengths"]([_row(7000)], _count, 6144)


def test_no_rows_is_an_error():
    with pytest.raises(ValueError):
        _helpers(6)["plan_lengths"]([], _count, 6144)


def test_truncate_policy_keeps_every_pair_at_the_ceiling():
    rows = [_row(100), _row(7000)]
    plan = _helpers(6)["plan_lengths"](rows, _count, 6144, policy="truncate")
    assert plan["dropped"] == [] and plan["keep"] == [0, 1]
    assert plan["max_seq_length"] == 6144
    assert plan["max_prompt_length"] < plan["max_seq_length"]


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        _helpers(6)["plan_lengths"]([_row(10)], _count, 6144, policy="shrug")


@pytest.mark.parametrize(
    ("gb", "ceiling"),
    [(0, 6144), (15.0, 6144), (22.5, 8192), (40.0, 12288), (80.0, 12288)],
)
def test_gpu_ceiling_by_memory(gb, ceiling):
    assert _helpers(6)["gpu_ceiling"](gb) == ceiling


def test_cell_6_sets_max_seq_length_from_the_plan_before_loading_the_model():
    source = _cell(6)
    assert "MAX_SEQ_LENGTH = LENGTH_PLAN[" in source
    assert source.index("LENGTH_PLAN =") < source.index(
        "FastLanguageModel.from_pretrained("
    )
    assert "MAX_SEQ_LENGTH = 2048" not in source
